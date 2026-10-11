"""In-app notification endpoints: list (with unread count) + mark read,
plus the Web Push device endpoints that replaced e-mail alerts."""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification, PushSubscription
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


class PushPublicKeyView(APIView):
    """GET /api/notifications/push/key/ — the VAPID public key + availability.

    The frontend reads this at subscribe time, so there is zero per-domain
    configuration in the bundle. `enabled:false` simply means the server has
    no VAPID key yet — the in-app bell keeps working either way.
    Public on purpose: a *public* key carries no secrets (like /api/stats).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from common.push import is_configured, public_key_b64url

        return Response(
            {
                "enabled": is_configured(),
                "public_key": public_key_b64url(),
            }
        )


class PushSubscribeView(APIView):
    """POST {endpoint, keys:{p256dh, auth}} — register this device.

    Re-subscribing the same endpoint simply rotates its owner/keys, so a
    re-login on the same browser never creates duplicate rows.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        endpoint = str(request.data.get("endpoint", "") or "").strip()
        keys = request.data.get("keys") or {}
        p256dh = str(keys.get("p256dh", "") or "").strip()
        auth = str(keys.get("auth", "") or "").strip()
        if not endpoint or not p256dh or not auth:
            return Response(
                {"detail": "بيانات الاشتراك غير مكتملة (endpoint/keys)."},
                status=400,
            )
        PushSubscription.objects.update_or_create(
            endpoint=endpoint[:500],
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "is_active": True,
            },
        )
        return Response({"detail": "تم تفعيل الإشعارات الفورية على هذا الجهاز."})


class PushUnsubscribeView(APIView):
    """POST {endpoint} — this device no longer wants pushes."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        endpoint = str(request.data.get("endpoint", "") or "")
        PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint
        ).delete()
        return Response({"detail": "تم إيقاف الإشعارات الفورية على هذا الجهاز."})
