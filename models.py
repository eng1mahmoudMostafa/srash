"""Moderation domain: reports and audit events."""
from django.conf import settings
from django.db import models


class Report(models.Model):
    class Reason(models.TextChoices):
        HARASSMENT = "harassment", "Harassment"
        SPAM = "spam", "Spam"
        THREAT = "threat", "Threat"
        HATE = "hate", "Hate"
        SEXUAL = "sexual", "Sexual content"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending"
        RESOLVED = "resolved"
        DISMISSED = "dismissed"

    message = models.ForeignKey(
        "messages_app.Message",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_reports",
        help_text="The recipient reporting the message.",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_reports",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report#{self.pk}:{self.reason}"


class AbuseEvent(models.Model):
    """Short-lived, HMAC'd source signal used for anti-abuse decisions.

    The raw IP is never stored; only a periodic HMAC signature with a TTL.
    """

    ip_hmac = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]