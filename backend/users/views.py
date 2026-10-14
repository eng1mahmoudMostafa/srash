import os
from datetime import timedelta

from django.conf import settings as dj_settings
from django.contrib.auth import (
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.rate import (
    RateLimitExceeded,
    check_login_rate_limit,
    check_password_rate_limit,
)
from users.models import Profile, Subscription, UserSettings
from users.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    PRESET_SECURITY_QUESTIONS,
    PasswordRecoverySerializer,
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
            {
                "id": user.pk,
                "username": user.username,
                "security_questions": PRESET_SECURITY_QUESTIONS,
            },
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


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ — proof of the current password.

    The caller's own session is kept alive (update_session_auth_hash) while
    every other session for this user is invalidated by the hash change.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Brute-force protection on the old-password guess.
            check_password_rate_limit(request, "pwdchange")
        except RateLimitExceeded as exc:
            return Response(
                {"detail": exc.message},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        return Response({"detail": "تم تغيير كلمة المرور بنجاح."})


class PasswordRecoveryStartView(APIView):
    """POST /api/auth/recovery/ — reveal the account's own security question.

    Unknown usernames and accounts without a question get the exact same
    body shape, so a prober can never tell registered names from free ones.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = str(request.data.get("username", "") or "").strip().lower()
        user = None
        if username:
            user = (
                User.objects.filter(username__iexact=username, is_active=True)
                .only("security_question", "security_answer_hash")
                .first()
            )
        question = ""
        if user is not None and user.has_security_question:
            question = user.security_question
        return Response(
            {"recoverable": bool(question), "security_question": question}
        )


class PasswordRecoveryConfirmView(APIView):
    """POST /api/auth/recovery-confirm/ — answer the question, set a new password.

    A wrong answer and an unknown username produce identical errors (the
    serializer guarantees it), so nobody can probe which accounts exist.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            check_password_rate_limit(request, "pwdrecover")
        except RateLimitExceeded as exc:
            return Response(
                {"detail": exc.message},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        serializer = PasswordRecoverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response(
            {"detail": "تم تعيين كلمة المرور الجديدة — سجّل دخولك الآن."}
        )

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
        # مزامنة: checkbox "السماح بالرسائل المجهولة" هو نفسه زر استقبال
        # الرسائل — كلاهما يتحكم في الحقل الفعلي accept_anonymous الذي
        # يفحصه إرسال الرسائل، حتى لا يظهر تعارض بين الحالة والزر.
        user = request.user
        if user.accept_anonymous != instance.allow_anonymous:
            user.accept_anonymous = instance.allow_anonymous
            user.save(update_fields=["accept_anonymous", "updated_at"])
        return Response(serializer.data)


class ToggleAnonymousView(APIView):
    """Temporarily pause receiving anonymous messages."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        user.accept_anonymous = not user.accept_anonymous
        user.save(update_fields=["accept_anonymous", "updated_at"])
        # مزامنة checkbox الخصوصية مع الزر (نظام واحد موحّد).
        us, _ = UserSettings.objects.get_or_create(user=user)
        if us.allow_anonymous != user.accept_anonymous:
            us.allow_anonymous = user.accept_anonymous
            us.save(update_fields=["allow_anonymous"])
        return Response({"accept_anonymous": user.accept_anonymous})


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
    """POST multipart 'avatar': validates, crops square, uploads to Catbox.

    الصورة تُنظف (تصغير + إزالة EXIF) ثم تُرفع على Catbox، ونخزن
    الرابط فقط — لا تستهلك أي مساحة على السيرفر.
    """

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

        # الرفع على Catbox بدل التخزين المحلي (توفير مساحة السيرفر)
        from common.catbox import upload_to_catbox

        try:
            url = upload_to_catbox(buf.getvalue(), "avatar.jpg")
        except RuntimeError:
            # فشل Catbox بعد إعادة المحاولة: نحفظ الصورة محليًا حتى لا تُفقد
            # (نفس منطق مرفقات الرسائل) — والعرض يتم من /media/ تلقائيًا.
            profile = Profile.objects.get_or_create(user=request.user)[0]
            if profile.avatar:
                try:
                    profile.avatar.delete(save=False)
                except Exception:
                    pass
            profile.avatar_url = ""
            profile.avatar.save(
                "avatar.jpg", ContentFile(buf.getvalue()), save=False
            )
            profile.save(update_fields=["avatar", "avatar_url"])
            return Response({"avatar_url": profile.avatar.url})

        profile = Profile.objects.get_or_create(user=request.user)[0]
        # حذف أي ملف محلي قديم (تنظيف نهائي) والاعتماد على الرابط
        if profile.avatar:
            try:
                profile.avatar.delete(save=False)
            except Exception:
                pass
            profile.avatar = None
        profile.avatar_url = url
        profile.save(update_fields=["avatar", "avatar_url"])
        return Response({"avatar_url": url})

    def delete(self, request):
        """Remove the account photo entirely (خيار إلغاء الصورة)."""
        profile = Profile.objects.get_or_create(user=request.user)[0]
        if profile.avatar:
            try:
                profile.avatar.delete(save=False)
            except Exception:
                pass
            profile.avatar = None
        if not profile.avatar_url and not profile.avatar:
            return Response(
                {"detail": "لا توجد صورة لإزالتها."},
                status=status.HTTP_404_NOT_FOUND,
            )
        profile.avatar_url = ""
        profile.save(update_fields=["avatar", "avatar_url"])
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
                "price_egp": dj_settings.PREMIUM_PRICE_EGP,
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