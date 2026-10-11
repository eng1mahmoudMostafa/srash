"""Custom user model and per-user privacy settings."""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models

from common.crypto import sign_ip


class User(AbstractUser):
    """Registration without e-mail is allowed (e-mail is optional)."""

    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        max_length=30,
        unique=True,
        help_text="Optional; the public slug used in shareable URLs.",
        validators=[username_validator],
    )
    email = models.EmailField(blank=True, null=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Password recovery WITHOUT e-mail: the question stays readable (it is
    # shown to the owner at recovery time), the answer only ever exists as a
    # salted PBKDF2 hash — never in plaintext (matches users/0006 migration).
    security_question = models.CharField(max_length=200, blank=True, default="")
    security_answer_hash = models.CharField(max_length=255, blank=True, default="")

    # Pause receiving anonymous messages (temporary block).
    accept_anonymous = models.BooleanField(default=True)

    # "آخر ظهور": refreshed by LastSeenMiddleware (max once per minute).
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def share_url(self, request=None) -> str:
        """Absolute public URL. When a request is available, build the URL
        from it so links copied on any domain/tunnel actually work — this
        fixes shared links pointing to http://localhost:8000."""
        path = f"/u/{self.username}"
        if request is not None:
            return request.build_absolute_uri(path)
        return f"{settings.SITE_BASE_URL}{path}"

    def __str__(self):
        return self.username

    @property
    def has_security_question(self) -> bool:
        """True when this account can be recovered via its own Q&A."""
        return bool(self.security_question and self.security_answer_hash)

    @staticmethod
    def _normalize_security_answer(value) -> str:
        """Collapse whitespace and fold the Arabic alef/yeh/teh-marbuta
        variants so a tiny spelling difference never locks the owner out."""
        text = " ".join(str(value or "").split())
        for variant, canonical in (
            ("أ", "ا"),
            ("إ", "ا"),
            ("آ", "ا"),
            ("ى", "ي"),
            ("ة", "ه"),
        ):
            text = text.replace(variant, canonical)
        return text

    def set_security_answer(self, answer) -> None:
        """Store the answer only as a salted PBKDF2 hash (never plaintext)."""
        from django.contrib.auth.hashers import make_password

        self.security_answer_hash = make_password(
            self._normalize_security_answer(answer)
        )

    def check_security_answer(self, answer) -> bool:
        """True when `answer` matches the stored hash (normalized first)."""
        if not self.security_answer_hash:
            return False
        from django.contrib.auth.hashers import check_password

        return check_password(
            self._normalize_security_answer(answer), self.security_answer_hash
        )


class Profile(models.Model):
    """Public profile metadata shown on the visitor-facing page."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    # رابط الصورة على استضافة خارجية (Catbox) — يوفر مساحة السيرفر.
    # عند وجوده يُستخدم بدل ملف avatar المحلي.
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    # Premium badge: granted while an approved subscription is running.
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.username


from secrets import token_hex


class Subscription(models.Model):
    """Manual premium plan (توثيق الحساب): pay EGP/month → owner approves."""

    class Status(models.TextChoices):
        PENDING = "pending"
        ACTIVE = "active"
        REJECTED = "rejected"
        EXPIRED = "expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    reference = models.CharField(max_length=24, unique=True, blank=True)
    amount_egp = models.PositiveIntegerField(default=100)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    transfer_note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"SRAH-{token_hex(4).upper()}"
        super().save(*args, **kwargs)

    def activate(self, days=None, now=None):
        from datetime import timedelta

        from django.conf import settings as dj_settings
        from django.utils import timezone

        now = now or timezone.now()
        self.status = self.Status.ACTIVE
        self.starts_at = now
        self.decided_at = now
        self.expires_at = now + timedelta(days=days or dj_settings.PREMIUM_DAYS)
        self.save(update_fields=[
            "status", "starts_at", "decided_at", "expires_at",
        ])
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.is_verified = True
        profile.save(update_fields=["is_verified"])

    def reject(self):
        from django.utils import timezone

        self.status = self.Status.REJECTED
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "decided_at"])
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.is_verified = False
        profile.save(update_fields=["is_verified"])


class UserSettings(models.Model):
    """Privacy and anti-abuse settings (MVP)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    allow_anonymous = models.BooleanField(default=True)
    # Enable per-source quiet-down: at most one message per period.
    gap_minutes = models.PositiveIntegerField(default=0)
    # Web Push alert on new messages: ON by default. Replaces the removed
    # e-mail alert (users/0006) — the browser delivers it, never the body.
    push_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings:{self.user_id}"