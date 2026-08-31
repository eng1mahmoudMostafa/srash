"""Anonymous message model.

Note: there is NO sender field. Messages are never tied to a sending account
or an IP address, preserving anonymity to the recipient.
"""
from django.conf import settings
from django.db import models


class Message(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active"
        DELETED = "deleted"
        FLAGGED = "flagged"

    # Recipient only. No sender, no IP.
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )

    # Payload is stored field-level encrypted (AES-256-GCM).
    body_ciphertext = models.TextField()
    body_nonce = models.CharField(max_length=128)

    # Optional name the SENDER chooses to include (also encrypted). It is
    # revealed to the recipient only while their premium subscription is
    # active; otherwise it stays encrypted and hidden. Still no sender
    # account and no IP â€” identity appears only if the sender writes it.
    sender_name_ciphertext = models.TextField(blank=True, default="")
    sender_name_nonce = models.CharField(max_length=128, blank=True, default="")

    # Sending requires an account; the sender's username is stored
    # ENCRYPTED (never a foreign key, never plaintext) so a premium
    # verified recipient can reveal it â€” without ever linking messages
    # to accounts in the database or exposing it to anyone else.
    sender_username_ciphertext = models.TextField(blank=True, default="")
    sender_username_nonce = models.CharField(max_length=128, blank=True, default="")

    # One-way HMAC fingerprint of the sender's username (never plaintext,
    # never reversible). Used ONLY so the sender can list/delete their own
    # sent messages â€” it cannot reveal who sent a message to anyone else.
    sender_fingerprint = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )

    # Optional image attached by the sender. Re-encoded server-side (EXIF/GPS
    # metadata stripped) and served ONLY to the recipient through an
    # authenticated endpoint â€” never as a public media URL.
    image = models.ImageField(upload_to="message_images/", blank=True, null=True)

    # Recipient's optional reply, stored encrypted the same way as the
    # body. The reply is decrypted for the recipient (inbox) and for the
    # original sender (sent page, matched by fingerprint) â€” nobody else.
    reply_ciphertext = models.TextField(blank=True, null=True, default="")
    reply_nonce = models.CharField(max_length=128, blank=True, default="")
    replied_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    @property
    def has_image(self) -> bool:
        return bool(self.image)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Message#{self.pk} -> {self.recipient_id}"