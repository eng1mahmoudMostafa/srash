import re

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from users.models import Profile, Subscription, User, UserSettings

# Real Arabic/Latin names only (no digits/symbols), at least two words.
_REAL_NAME_RE = re.compile(r"^[\u0621-\u064A\u0670-\u06D3a-zA-Z '’\u0640]{2,60}$")


def validate_real_name(value):
    value = re.sub(r"\s+", " ", str(value)).strip()
    if not value:
        return ""
    if not _REAL_NAME_RE.match(value):
        raise serializers.ValidationError(
            "الاسم الحقيقي فقط: حروف عربية أو إنجليزية ومسافات، بدون أرقام أو رموز."
        )
    words = [w for w in value.split(" ") if len(w) >= 2]
    if len(words) < 2:
        raise serializers.ValidationError("اكتب الاسم الأول والأخير على الأقل.")
    return value


# Common Django password-validator messages, translated to Arabic so the
# register form never shows raw English errors (esp. the e-mail similarity
# one — the reported "error when registering with an e-mail").
_PASSWORD_AR = {
    "The password is too similar to the email address.":
        "كلمة المرور مشابهة جدًا لبريدك الإلكتروني — اختر كلمة مختلفة.",
    "The password is too similar to the username.":
        "كلمة المرور مشابهة جدًا لاسم المستخدم — اختر كلمة مختلفة.",
    "This password is too short. It must contain at least 8 characters.":
        "كلمة المرور قصيرة جدًا: 8 أحرف على الأقل.",
    "This password is too common.":
        "كلمة المرور شائعة جدًا — اختر كلمة أقوى.",
    "This password is entirely numeric.":
        "كلمة المرور أرقام فقط — أضف حروفًا.",
}


def validate_password_ar(value, user=None):
    """Run Django's validators but always surface Arabic messages."""
    try:
        validate_password(value, user=user)
    except DjangoValidationError as exc:
        messages = [
            _PASSWORD_AR.get(str(m), str(m)) for m in exc.messages
        ]
        raise serializers.ValidationError(messages)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        style={"input_type": "password"},
        validators=[validate_password_ar],
    )
    # Optional but encouraged: enables e-mail notifications & verification.
    email = serializers.EmailField(required=False, allow_blank=True)
    # REQUIRED: the account's real public name (first + last, letters only).
    full_name = serializers.CharField(write_only=True, max_length=60)

    class Meta:
        model = User
        fields = ["username", "password", "email", "full_name"]

    def validate_username(self, value):
        return value.strip().lower()

    def validate_full_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError(
                "الاسم الحقيقي مطلوب: اكتب اسمك الأول والأخير."
            )
        return validate_real_name(value)

    def validate_email(self, value):
        value = (value or "").strip()
        if not value:
            return None
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("هذا البريد مستخدم بالفعل بحساب آخر.")
        return value.lower()

    def create(self, validated_data):
        email = validated_data.pop("email", None)
        full_name = validated_data.pop("full_name", "")
        user = User(username=validated_data["username"], email=email or None)
        user.set_password(validated_data["password"])
        user.save()
        # The real name is a required registration step: it seeds the
        # public profile's display name immediately.
        Profile.objects.create(user=user, display_name=full_name)
        UserSettings.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs.get("username", "").strip(),
            password=attrs.get("password", ""),
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError(
                {"detail": "كلمة المرور أو اسم المستخدم غير صحيح."}
            )
        attrs["user"] = user
        return attrs


class MeSerializer(serializers.ModelSerializer):
    """Self view incl. e-mail status + premium verification badge."""

    is_verified = serializers.SerializerMethodField()
    shareable_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "email_verified",
            "is_verified", "shareable_url", "created_at",
        ]

    def get_is_verified(self, obj):
        prof = getattr(obj, "profile", None)
        return bool(prof and prof.is_verified)

    def get_shareable_url(self, obj):
        request = self.context.get("request")
        return obj.share_url(request)


class EmailUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email"]

    def validate_email(self, value):
        value = (value or "").strip().lower()
        if not value:
            raise serializers.ValidationError("اكتب بريدًا إلكترونيًا صحيحًا.")
        clash = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("هذا البريد مستخدم بالفعل بحساب آخر.")
        return value


class UserSerializer(serializers.ModelSerializer):
    shareable_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "created_at", "shareable_url"]

    def get_shareable_url(self, obj):
        request = self.context.get("request")
        return obj.share_url(request)


def _humanize_last_seen(dt):
    """Arabic relative "last seen" text."""
    from django.utils import timezone

    if not dt:
        return None
    secs = max(0, (timezone.now() - dt).total_seconds())
    if secs < 120:
        return "متصل الآن"
    if secs < 3600:
        return f"آخر ظهور قبل {int(secs // 60)} دقيقة"
    if secs < 86400:
        return f"آخر ظهور قبل {int(secs // 3600)} ساعة"
    days = int(secs // 86400)
    if days == 1:
        return "آخر ظهور أمس"
    return f"آخر ظهور قبل {days} يوم"


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    avatar_url = serializers.SerializerMethodField()
    can_receive = serializers.BooleanField(source="user.accept_anonymous", read_only=True)
    shareable_url = serializers.SerializerMethodField()
    last_seen_at = serializers.DateTimeField(
        source="user.last_seen_at", read_only=True
    )
    last_seen_human = serializers.SerializerMethodField()
    online = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "username",
            "display_name",
            "bio",
            "avatar_url",
            "is_verified",
            "can_receive",
            "shareable_url",
            "last_seen_at",
            "last_seen_human",
            "online",
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            try:
                # Cache-busting: إضافة إصدار يتغير مع كل تعديل للصورة
                # حتى يعرض المتصفح الصورة الجديدة فورًا ولا يُبقي القديمة.
                version = int(obj.updated_at.timestamp()) if obj.updated_at else 0
                return f"{obj.avatar.url}?v={version}"
            except ValueError:
                return None
        return None

    def get_online(self, obj):
        from django.utils import timezone

        ls = obj.user.last_seen_at
        return bool(ls) and (timezone.now() - ls).total_seconds() < 120

    def get_last_seen_human(self, obj):
        return _humanize_last_seen(obj.user.last_seen_at)

    def get_shareable_url(self, obj):
        request = self.context.get("request")
        path = f"/u/{obj.user.username}"
        if request is not None:
            return request.build_absolute_uri(path)
        return path


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Owner edits their public profile; display_name must be a real name."""

    class Meta:
        model = Profile
        fields = ["display_name", "bio"]

    def validate_display_name(self, value):
        return validate_real_name(value)


class SubscriptionSerializer(serializers.ModelSerializer):
    remaining_days = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "reference", "status", "amount_egp", "transfer_note",
            "created_at", "expires_at", "remaining_days",
        ]

    def get_remaining_days(self, obj):
        from datetime import timedelta

        from django.utils import timezone

        if obj.status != Subscription.Status.ACTIVE or not obj.expires_at:
            return None
        left = obj.expires_at - timezone.now()
        return max(0, left.days)


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            "allow_anonymous",
            "gap_minutes",
            "notify_new_message",
        ]