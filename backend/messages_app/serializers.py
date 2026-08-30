from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from common.crypto import decrypt_message, encrypt_message, sender_fingerprint
from common.spam import should_auto_flag
from messages_app.models import Message
from users.models import Subscription
from users.serializers import validate_real_name

User = get_user_model()


def _recipient_can_reveal(recipient) -> bool:
    """Premium gate: the sender's chosen name is shown only to recipients
    with a verified profile AND an active subscription."""
    prof = getattr(recipient, "profile", None)
    if prof is None or not prof.is_verified:
        return False
    return Subscription.objects.filter(
        user=recipient,
        status=Subscription.Status.ACTIVE,
        expires_at__gt=timezone.now(),
    ).exists()


class SendMessageSerializer(serializers.Serializer):
    """Visitor-facing payload. No sender identity is captured or stored."""

    username = serializers.CharField(write_only=True)
    message = serializers.CharField(
        write_only=True,
        max_length=settings.MAX_MESSAGE_LENGTH,
        min_length=1,
        trim_whitespace=False,
    )
    # Optional. Stored encrypted; revealed to the recipient only while
    # their premium (توثيق الحساب) subscription is active. Blank/omitted
    # values are accepted (the visitor stays fully anonymous).
    sender_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=60
    )
    # Optional attached image (sanitized before storage).
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)

    def validate_message(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("الرسالة لا يمكن أن تكون فارغة.")
        return value

    def validate_sender_name(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        # Real human names only (same rule as profile display names).
        return validate_real_name(value)

    def validate_image(self, value):
        """Sanitize: 5MB cap, re-encode as JPEG (strips EXIF/GPS), ≤1600px."""
        if value is None:
            return None
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                "حجم الصورة يجب أن يكون أقل من 5 ميجابايت."
            )
        from io import BytesIO

        from PIL import Image, ImageOps

        try:
            img = Image.open(value)
            img.load()
        except Exception:
            raise serializers.ValidationError("ملف الصورة غير صالح.")
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img.thumbnail((1600, 1600), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        from django.core.files.base import ContentFile

        return ContentFile(buf.getvalue(), name="attach.jpg")

    def validate(self, attrs):
        username = attrs["username"].strip().lower()
        recipient = (
            User.objects.filter(username=username, is_active=True).first()
        )
        if recipient is None:
            raise serializers.ValidationError(
                {"username": "المستخدم غير موجود."}
            )
        attrs["recipient"] = recipient
        return attrs

    def create(self, validated_data):
        recipient = validated_data["recipient"]
        plaintext = validated_data["message"]

        status = (
            Message.Status.FLAGGED
            if should_auto_flag(plaintext)
            else Message.Status.ACTIVE
        )
        ciphertext, nonce = encrypt_message(plaintext)

        name_plain = validated_data.get("sender_name", "")
        name_cipher, name_nonce = "", ""
        if name_plain:
            name_cipher, name_nonce = encrypt_message(name_plain)

        # The sender is always a logged-in account now; its username is
        # stored encrypted so a premium recipient can reveal it.
        # (DRF merges save(sender_user=...) into validated_data.)
        sender_user = validated_data.pop("sender_user", None)
        username_cipher, username_nonce = "", ""
        if sender_user is not None:
            username_cipher, username_nonce = encrypt_message(
                sender_user.username
            )

        return Message.objects.create(
            recipient=recipient,
            body_ciphertext=ciphertext,
            body_nonce=nonce,
            sender_name_ciphertext=name_cipher,
            sender_name_nonce=name_nonce,
            sender_username_ciphertext=username_cipher,
            sender_username_nonce=username_nonce,
            sender_fingerprint=(
                sender_fingerprint(sender_user.username)
                if sender_user is not None
                else ""
            ),
            image=validated_data.get("image"),
            status=status,
        )


class MessageSerializer(serializers.ModelSerializer):
    """Read-side view; decrypts the body for the authorized recipient."""

    message = serializers.SerializerMethodField()
    sender_name = serializers.SerializerMethodField()
    has_sender_name = serializers.SerializerMethodField()
    sender_username = serializers.SerializerMethodField()
    has_sender_username = serializers.SerializerMethodField()
    has_image = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "message", "is_read", "status", "created_at",
            "sender_name", "has_sender_name",
            "sender_username", "has_sender_username",
            "has_image",
        ]

    def get_has_image(self, obj):
        return bool(obj.image)

    def get_message(self, obj):
        try:
            return decrypt_message(obj.body_ciphertext, obj.body_nonce)
        except Exception:
            return None  # never leak an error to the client

    def get_has_sender_name(self, obj):
        return bool(obj.sender_name_ciphertext)

    def get_has_sender_username(self, obj):
        return bool(obj.sender_username_ciphertext)

    def _decrypt_sender_field(self, obj, cipher, nonce):
        if not cipher:
            return None
        if not _recipient_can_reveal(obj.recipient):
            return None
        try:
            return decrypt_message(cipher, nonce)
        except Exception:
            return None

    def get_sender_name(self, obj):
        """Shown only when the sender chose to include a name AND the
        recipient currently has an active premium (توثيق) subscription."""
        return self._decrypt_sender_field(
            obj, obj.sender_name_ciphertext, obj.sender_name_nonce
        )

    def get_sender_username(self, obj):
        """The sender's account username (stored encrypted) — revealed to
        the recipient under the same premium (توثيق) gate as the name."""
        return self._decrypt_sender_field(
            obj, obj.sender_username_ciphertext, obj.sender_username_nonce
        )


class SentMessageSerializer(serializers.ModelSerializer):
    """Read-side view of the sender's OWN sent messages.

    The sender is the author of the body, so it is decrypted for them.
    The recipient's username is shown (they own the inbox page).
    """

    message = serializers.SerializerMethodField()
    recipient_username = serializers.CharField(source="recipient.username", read_only=True)
    has_image = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "message", "recipient_username", "is_read", "status",
            "created_at", "has_image",
        ]

    def get_message(self, obj):
        try:
            return decrypt_message(obj.body_ciphertext, obj.body_nonce)
        except Exception:
            return None  # never leak an error to the client

    def get_has_image(self, obj):
        return bool(obj.image)