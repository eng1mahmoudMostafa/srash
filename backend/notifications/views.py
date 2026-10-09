"""In-app notification endpoints: list (with unread count) + mark read."""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification
from notifications.serializers import NotificationSerializer

# Only the newest entries are shown in the bell dropdown.
PAGE_SIZE = 20


class NotificationListView(APIView):
    """GET /api/notifications/ — the caller's latest notifications."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)
        unread = qs.filter(is_read=False).count()
        results = NotificationSerializer(qs[:PAGE_SIZE], many=True).data
        return Response({"results": results, "unread": unread})


class MarkNotificationReadView(APIView):
    """POST /api/notifications/<id>/read/ — mark ONE notification as read."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        # recipient filter prevents touching someone else's notification.
        Notification.objects.filter(
            pk=pk, recipient=request.user, is_read=False
        ).update(is_read=True)
        unread = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({"unread": unread})


class MarkAllNotificationsReadView(APIView):
    """POST /api/notifications/read-all/ — clear the whole badge at once."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        return Response({"unread": 0})
