"""Views for sending and managing anonymous messages.

Sending REQUIRES a registered, logged-in account — but the message is
still never tied to the account in plaintext: no sender foreign key, no
IP. The sender's username is stored encrypted and revealed only to a
premium verified recipient. Reading/management requires the recipient's
session. Soft-delete is used for deletion.
"""
import logging

from django.http import FileResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from common.rate import RateLimitExceeded, check_message_rate_limit
from messages_app.models import Message
from messages_app.serializers import MessageSerializer, SendMessageSerializer

logger = logging.getLogger(__name__)


def _perform_send(request):
    """Validate input, enforce limits and privacy flags, then persist."""
    try:
        check_message_rate_limit(request)
    except RateLimitExceeded as exc:
        return Response(
            {"detail": exc.message},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    recipient = serializer.validated_data["recipient"]
    if recipient == request.user:
        return Response(
            {"detail": "لا يمكنك إرسال رسالة إلى نفسك."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not recipient.accept_anonymous:
        return Response(
            {"detail": "هذا المستخدم أوقف استقبال الرسائل المجهولة."},
            status=status.HTTP_403_FORBIDDEN,
        )

    saved_message = serializer.save(sender_user=request.user)

    # Privacy-safe e-mail nudge: never includes the message body/sender.
    # Sent in the background so SMTP latency can't slow the request.
    try:
        from common.mail import notify_new_message, send_async

        send_async(notify_new_message, recipient)
    except Exception:
        logger.warning("new-message e-mail notification failed", exc_info=True)

    return Response(
        {"success": True, "message": "تم إرسال الرسالة بنجاح."},
        status=status.HTTP_201_CREATED,
    )


class MessageSendView(APIView):
    """POST /api/messages/ — registered, logged-in senders only.

    The message stays anonymous to the recipient: no sender account is
    linked in plaintext, and the sender's username is stored encrypted.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return _perform_send(request)


class MessageListView(APIView):
    """GET /api/messages/ — inbox for the authenticated recipient."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = Message.objects.filter(
            recipient=request.user,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        serializer = MessageSerializer(queryset, many=True)
        return Response({"results": serializer.data})


class MessageDetailView(APIView):
    """GET one / PATCH mark-as-read / DELETE (soft delete)."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, request, pk):
        return get_object_or_404(
            Message,
            pk=pk,
            recipient=request.user,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )

    def get(self, request, pk):
        message = self.get_object(request, pk)
        return Response(MessageSerializer(message).data)

    def patch(self, request, pk):
        message = self.get_object(request, pk)
        message.is_read = True
        message.save(update_fields=["is_read"])
        return Response(MessageSerializer(message).data)

    def delete(self, request, pk):
        message = self.get_object(request, pk)
        # Soft delete: retain the row until retention purge, but hide it now.
        message.status = Message.Status.DELETED
        message.deleted_at = timezone.now()
        message.save(update_fields=["status", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageImageView(APIView):
    """GET /api/messages/<id>/image/ — recipient-only attached image.

    The stored file is re-encoded server-side on upload (EXIF/GPS metadata
    stripped) and served ONLY to the owning recipient through this
    authenticated endpoint — never as a public media URL. 404 (not 403) for
    anything else so message existence is not revealed to other accounts.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        message = get_object_or_404(
            Message,
            pk=pk,
            recipient=request.user,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        if not message.image:
            return Response(
                {"detail": "لا توجد صورة مرفقة بهذه الرسالة."},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = FileResponse(
            message.image.open("rb"), content_type="image/jpeg"
        )
        response["Content-Disposition"] = f'inline; filename="msg-{pk}.jpg"'
        return response