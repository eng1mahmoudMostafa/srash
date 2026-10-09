from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Privacy-safe: never exposes the message body — only the kind + state."""

    class Meta:
        model = Notification
        fields = ["id", "kind", "is_read", "created_at"]
