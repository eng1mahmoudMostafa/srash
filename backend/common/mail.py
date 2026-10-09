"""Transactional e-mails. No message *content* ever leaves the platform."""
import logging

import os
import threading

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _sanitize_header_value(value: str) -> str:
    """Strip CR/LF to prevent SMTP header injection via user-controlled
    fields (username / display name rendered into the e-mail body)."""
    return "".join(value.replace("\r", "").replace("\n", "").splitlines())

VERIFY_SALT = "users.email.verify.v1"
# Reset tokens live only 1 hour (confirmed in PasswordResetConfirmView).
PASSWORD_RESET_SALT = "users.password.reset.v1"


def send_async(fn, *args):
    """Fire-and-forget e-mail in a background thread so a slow/unreachable
    SMTP server never blocks or breaks the HTTP request."""

    def _worker():
        try:
            fn(*args)
        except Exception:
            logger.warning("async e-mail failed", exc_info=True)

    if settings.EMAIL_BACKEND.endswith(
        ("console.EmailBackend", "locmem.EmailBackend")
    ):
        # No real SMTP configured (or in a test): run inline so it shows in
        # server logs / lands in the test outbox.
        try:
            fn(*args)
        except Exception:
            logger.warning("e-mail failed", exc_info=True)
        return
    threading.Thread(target=_worker, daemon=True).start()


def _verification_link(user):
    token = signing.dumps({"uid": user.pk}, salt=VERIFY_SALT)
    return f"{settings.SITE_BASE_URL}/api/auth/verify-email/?t={token}"


def send_email_verification_email(user):
    """Ask the user to confirm ownership of their address."""
    if not user.email:
        return False
    link = _verification_link(user)
    send_mail(
        subject="وثّق بريدك الإلكتروني على صراحة",
        message=(
            f"مرحبًا {_sanitize_header_value(user.username)}!\n\n"
            f"اضغط الرابط لتأكيد أن هذا البريد لك:\n{link}\n\n"
            "الرابط صالح 48 ساعة.\n\nفريق صراحة."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return True


def send_password_reset_email(user):
    """E-mail a 1-hour reset link. Opens the SPA page (not the API) and,
    like every e-mail here, never carries any message content."""
    if not user.email:
        return False
    token = signing.dumps({"uid": user.pk}, salt=PASSWORD_RESET_SALT)
    link = f"{settings.SITE_BASE_URL}/reset-password?t={token}"
    send_mail(
        subject="إعادة تعيين كلمة مرورك على صراحة",
        message=(
            f"مرحبًا {_sanitize_header_value(user.username)} 👋\n\n"
            "استلمنا طلبًا لإعادة تعيين كلمة المرور. افتح الرابط لاختيار كلمة جديدة:\n"
            f"{link}\n\n"
            "الرابط صالح لمدة ساعة واحدة فقط.\n"
            "إذا لم تطلب هذا، تجاهل هذه الرسالة — لن يتغيّر شيء.\n\nفريق صراحة."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return True


def notify_new_message(recipient_user):
    """Privacy-safe alert: never includes the message body or sender."""
    if not recipient_user.email:
        return False
    from users.models import UserSettings

    # get_or_create: accounts without a settings row (created before the
    # setting existed, or via admin) fall back to the default (ON) instead
    # of silently never receiving the alert.
    us, _ = UserSettings.objects.get_or_create(user=recipient_user)
    if not us.notify_new_message:
        return False
    display = getattr(recipient_user, "profile", None)
    display = getattr(display, "display_name", "") or recipient_user.username
    send_mail(
        subject="لديك رسالة جديدة على صراحة",
        message=(
            f"مرحبًا {_sanitize_header_value(display)} 👋\n\n"
            "وصلتك رسالة مجهولة جديدة على صفحتك:\n"
            f"{recipient_user.share_url()}\n\n"
            "نرسل التنبيه فقط دون محتوى الرسالة حفاظًا على خصوصيتك.\n\nفريق صراحة."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_user.email],
        fail_silently=False,
    )
    return True