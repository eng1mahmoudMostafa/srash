import os
from datetime import timedelta

from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model, login, logout
from django.core import signing
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.mail import (
    VERIFY_SALT,
    send_email_verification_email,
)
from common.rate import RateLimitExceeded, check_login_rate_limit
from users.models import Profile, Subscription, UserSettings
from users.serializers import (
    EmailUpdateSerializer,
    LoginSerializer,
    MeSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    SubscriptionSerializer,
    UserSerializer,
    UserSettingsSerializer,
)

User = get_user_model()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    """Rotates/ensures the CSRF cookie so the SPA can send mutations."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"csrf": "set"})


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            UserSerializer(user, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        try:
            check_login_rate_limit(request)
        except RateLimitExceeded as exc:
            return Response(
                {"detail": exc.message},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = LoginSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(UserSerializer(user, context={"request": request}).data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user, context={"request": request}).data)

    def patch(self, request):
        """Update e-mail address (resets verification until re-confirmed)."""
        serializer = EmailUpdateSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.email_verified = False
        user.save(update_fields=["email_verified"])
        return Response(MeSerializer(user, context={"request": request}).data)


class SendVerificationEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.email:
            return Response({"detail": "أضف بريدك الإلكتروني أولًا."}, status=400)
        from common.mail import send_async

        send_async(send_email_verification_email, request.user)
        return Response({"detail": "تم إرسال رابط التوثيق إلى بريدك."})


class PublicProfileView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, username):
        user = (
            User.objects.filter(username=username, is_active=True)
            .first()
        )
        if user is None:
            return Response(
                {"detail": "المستخدم غير موجود."}, status=status.HTTP_404_NOT_FOUND
            )
        profile, _ = Profile.objects.get_or_create(user=user)
        return Response(ProfileSerializer(profile).data)


class UserSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_instance(self, user):
        obj, _ = UserSettings.objects.get_or_create(user=user)
        return obj

    def get(self, request):
        return Response(UserSettingsSerializer(self._get_instance(request.user)).data)

    def patch(self, request):
        instance = self._get_instance(request.user)
        serializer = UserSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ToggleAnonymousView(APIView):
    """Temporarily pause receiving anonymous messages."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        user.accept_anonymous = not user.accept_anonymous
        user.save(update_fields=["accept_anonymous", "updated_at"])
        return Response({"accept_anonymous": user.accept_anonymous})


class VerifyEmailTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get("t", "")
        ok = False
        try:
            data = signing.loads(token, salt=VERIFY_SALT, max_age=60 * 60 * 48)
            user = User.objects.filter(pk=data.get("uid")).first()  # noqa: F821
        except Exception:
            user = None
        if user is not None:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
            ok = True
        body = (
            "<h2>✅ تم توثيق بريدك بنجاح.</h2><p><a href='/settings'>عودة للإعدادات</a></p>"
            if ok
            else "<h2>❌ الرابط غير صالح أو انتهت صلاحيته.</h2>"
        )
        html = (
            "<html dir='rtl' lang='ar'><body style=\"font-family:sans-serif;"
            f"text-align:center;padding-top:70px\">{body}</body></html>"
        )
        return HttpResponse(html)


class MyProfileView(APIView):
    """GET / PATCH my public profile (real-name validation applies)."""

    permission_classes = [permissions.IsAuthenticated]

    def _profile(self, user):
        return Profile.objects.get_or_create(user=user)[0]

    def get(self, request):
        return Response(ProfileSerializer(self._profile(request.user)).data)

    def patch(self, request):
        profile = self._profile(request.user)
        serializer = ProfileUpdateSerializer(
            profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProfileSerializer(profile).data)


class AvatarUploadView(APIView):
    """POST multipart 'avatar': validates, crops square, stores max 512px."""

    permission_classes = [permissions.IsAuthenticated]
    MAX_BYTES = 3 * 1024 * 1024
    ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

    def post(self, request):
        upload = request.FILES.get("avatar")
        if upload is None:
            return Response({"detail": "أرفق الصورة في الحقل avatar."}, status=400)
        if upload.size > self.MAX_BYTES:
            return Response({"detail": "الحد الأقصى لحجم الصورة 3 ميجابايت."}, status=400)
        ext = os.path.splitext(upload.name)[1].lower()
        if ext not in self.ALLOWED_EXT:
            return Response(
                {"detail": "الصيغ المسموحة: JPG أو PNG أو WEBP."}, status=400
            )
        # Verify the magic bytes match the declared extension (blocks
        # disguised executables/scripts with an image extension).
        header = upload.file.read(16)
        upload.file.seek(0)
        _MAGIC = (
            b"\xff\xd8\xff",          # JPEG
            b"\x89PNG\r\n\x1a\n",      # PNG
            b"RIFF",                    # WEBP
        )
        if not header.startswith(_MAGIC):
            return Response({"detail": "ملف الصورة غير صالح."}, status=400)

        from io import BytesIO

        from PIL import Image, ImageOps

        try:
            img = Image.open(upload)
            img.load()
        except Exception:
            return Response({"detail": "ملف الصورة غير صالح."}, status=400)

        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img = ImageOps.fit(img, (512, 512), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)

        profile = Profile.objects.get_or_create(user=request.user)[0]
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.avatar.save(
            f"avatars/u{request.user.id}.jpg", ContentFile(buf.getvalue())
        )
        return Response({"avatar_url": profile.avatar.url})

    def delete(self, request):
        """Remove the account photo entirely (خيار إلغاء الصورة)."""
        profile = Profile.objects.get_or_create(user=request.user)[0]
        if not profile.avatar:
            return Response(
                {"detail": "لا توجد صورة لإزالتها."},
                status=status.HTTP_404_NOT_FOUND,
            )
        profile.avatar.delete(save=False)
        profile.avatar = None
        profile.save(update_fields=["avatar"])
        return Response({"detail": "تمت إزالة صورة الحساب.", "avatar_url": None})


class SubscribeCreateView(APIView):
    """Request premium (توثيق الحساب): creates a pending subscription."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        active_sub = (
            Subscription.objects.filter(
                user=request.user,
                status=Subscription.Status.ACTIVE,
                expires_at__gt=timezone.now(),
            )
            .order_by("-expires_at")
            .first()
        )
        if active_sub is not None:
            return Response(
                {
                    "status": "active",
                    "subscription": SubscriptionSerializer(active_sub).data,
                }
            )

        note = ""
        if isinstance(request.data, dict):
            note = str(request.data.get("transfer_note", "")).strip()[:120]

        # Capacity guard: refuse new requests when today's/month's slots
        # are exhausted (counted from approved subscriptions).
        now = timezone.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_used = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE, decided_at__gte=day_start
        ).count()
        month_used = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE, decided_at__gte=month_start
        ).count()
        if day_used >= dj_settings.SUB_SLOTS_DAY:
            return Response(
                {"detail": "اكتمل العدد المسموح من الاشتراكات اليوم — حاول غدًا."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if month_used >= dj_settings.SUB_SLOTS_MONTH:
            return Response(
                {"detail": "اكتمل العدد المسموح من الاشتراكات هذا الشهر."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Cooldown: one request per user every SUB_COOLDOWN_HOURS.
        cooldown = timedelta(hours=dj_settings.SUB_COOLDOWN_HOURS)
        last_sub = (
            Subscription.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )
        if last_sub is not None:
            elapsed = timezone.now() - last_sub.created_at
            if elapsed < cooldown:
                minutes_left = max(
                    1, int((cooldown - elapsed).total_seconds() // 60) + 1
                )
                if minutes_left >= 60:
                    hours_left = (minutes_left + 59) // 60
                    wait = f"{hours_left} ساعة"
                else:
                    wait = f"{minutes_left} دقيقة"
                return Response(
                    {
                        "detail": (
                            "أرسلت طلب اشتراك بالفعل — يمكنك إرسال طلب جديد "
                            f"بعد {wait}."
                        )
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        sub = Subscription.objects.create(
            user=request.user,
            amount_egp=dj_settings.PREMIUM_PRICE_EGP,
            transfer_note=note,
        )
        return Response(
            {
                "status": sub.status,
                "reference": sub.reference,
                "amount_egp": sub.amount_egp,
                "payment_info": dj_settings.PAYMENT_INFO,
                "detail": (
                    "حوّل المبلغ على بيانات الدفع أعلاه واذكر الرقم المرجعي، "
                    "ثم سيوافق المشرف من لوحة الإدارة خلال وقت قصير."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class SubscriptionStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subs = Subscription.objects.filter(user=request.user)[:5]
        profile = Profile.objects.get_or_create(user=request.user)[0]
        has_active = any(
            s.status == Subscription.Status.ACTIVE
            and s.expires_at
            and s.expires_at > timezone.now()
            for s in subs
        )
        # Remaining subscription capacity (decrements with each approval).
        now = timezone.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_used = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE, decided_at__gte=day_start
        ).count()
        month_used = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE, decided_at__gte=month_start
        ).count()
        slots = {
            "day_limit": dj_settings.SUB_SLOTS_DAY,
            "day_remaining": max(0, dj_settings.SUB_SLOTS_DAY - day_used),
            "month_limit": dj_settings.SUB_SLOTS_MONTH,
            "month_remaining": max(0, dj_settings.SUB_SLOTS_MONTH - month_used),
        }
        return Response(
            {
                "is_verified": bool(profile.is_verified and has_active),
                "payment_info": dj_settings.PAYMENT_INFO,
                "slots": slots,
                "results": SubscriptionSerializer(subs, many=True).data,
            }
        )


class GlobalStatsView(APIView):
    """Public counts shown on the homepage."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(
            {
                "user_count": User.objects.filter(is_active=True).count(),
            }
        )