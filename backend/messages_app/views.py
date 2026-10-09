"""Views for sending and managing anonymous messages.

Sending REQUIRES a registered, logged-in account — but the message is
still never tied to the account in plaintext: no sender foreign key, no
IP. The sender's username is stored encrypted and revealed only to a
premium verified recipient. Reading/management requires the recipient's
session. Soft-delete is used for deletion.

Delivery alerts are in-app (the bell) plus an instant Web Push, never an
e-mail — the platform never collects an address.
"""
import logging
import threading

from django.http import FileResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from common.rate import RateLimitExceeded, check_message_rate_limit
from messages_app.models import Message
from messages_app.serializers import (
    MessageSerializer,
    SendMessageSerializer,
    SentMessageSerializer,
)
from notifications.models import Notification
from users.models import Subscription

logger = logging.getLogger(__name__)

def _paginate(request, queryset, serializer_cls, default_size=20, max_size=50):
    """Slice a queryset into a page envelope for the SPA.

    `results` keeps the original shape so a caller that ignores pagination
    still works; the extra keys power the "load more" button.
    """
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get("page_size", default_size))
    except (TypeError, ValueError):
        page_size = default_size
    page_size = max(1, min(max_size, page_size))

    total = queryset.count()
    start = (page - 1) * page_size
    chunk = list(queryset[start : start + page_size])
    return {
        "results": serializer_cls(chunk, many=True).data,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": start + page_size < total,
        "has_prev": page > 1,
    }

def _push_async(recipient) -> None:
    """Fire-and-forget Web Push: never raises into the thread machinery.

    A push is a *bonus* — the in-app bell row above is the source of truth,
    so any failure here is only logged and the HTTP response is untouched.
    """
    from common.push import notify_new_message

    try:
        notify_new_message(recipient)
    except Exception:
        logger.warning("async push failed", exc_info=True)


def _dispatch_push(recipient) -> None:
    """Run the fire-and-forget push worker for `recipient`.

    Indirection (not an inline ``threading.Thread`` call) so tests can patch
    ``messages_app.views._dispatch_push`` and run it synchronously inside the
    test transaction — daemon threads cannot see uncommitted test data on
    SQLite. Production always goes through a daemon thread.

    Central guard: never spawn a thread against a test database at all.
    The dedicated push test opts in explicitly by patching this hook with
    a synchronous side effect; every other test stays silent and fast.
    """
    from django.db import connection

    db_name = str(connection.settings_dict.get("NAME", ""))
    if db_name.startswith(("test_", ":memory:", "file:memorydb")):
        return
    threading.Thread(
        target=_push_async, args=(recipient,), daemon=True
    ).start()


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

    # In-app notification (privacy-safe: kind only, no body/sender). Created
    # before the push step so the bell badge is never skipped by push issues.
    try:
        Notification.objects.create(
            recipient=recipient,
            kind="new_message",
            message=saved_message,
        )
    except Exception:
        logger.warning("in-app notification create failed", exc_info=True)

    # Instant browser push (works even with the site is closed). Runs in a
    # background thread so an unreachable push service never delays the
    # response; a failure here is silent — the bell above is the fallback.
    # NOTE: goes through _dispatch_push (not threading.Thread directly) so
    # tests can patch it to run synchronously; daemon threads cannot see
    # uncommitted test data on SQLite.
    _dispatch_push(recipient)

    return Response(
        MessageSerializer(saved_message, context={"request": request}).data,
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
        return Response(_paginate(request, queryset, MessageSerializer))

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
        # Keep the bell badge in sync: the message this notification points
        # at has now been read.
        Notification.objects.filter(
            message=message, is_read=False
        ).update(is_read=True)
        return Response(MessageSerializer(message).data)

    def delete(self, request, pk):
        message = self.get_object(request, pk)
        # Soft delete: retain the row until retention purge, but hide it now.
        message.status = Message.Status.DELETED
        message.deleted_at = timezone.now()
        message.save(update_fields=["status", "deleted_at"])
        # Drop its notifications so the bell never points at a dead message.
        Notification.objects.filter(message=message).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class SentMessagesView(APIView):
    """GET /api/messages/sent/ — the sender's own sent messages.

    Matched via a one-way fingerprint (never plaintext, never reversible)
    so listing sent messages cannot compromise the anonymity guarantee.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from common.crypto import sender_fingerprint

        fp = sender_fingerprint(request.user.username)
        queryset = Message.objects.filter(
            sender_fingerprint=fp,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        return Response(_paginate(request, queryset, SentMessageSerializer))

class SentMessageDeleteForRecipientView(APIView):
    """DELETE /api/messages/<id>/delete-for-recipient/ — premium feature.

    Allows the sender (with an active توثيق subscription) to remove their
    sent message from the recipient's inbox (soft delete). The message
    is matched by fingerprint so only its true author can delete it.
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        from django.utils import timezone as tz

        # Premium gate on the SENDER: verified profile + active subscription.
        prof = getattr(request.user, "profile", None)
        has_active_sub = Subscription.objects.filter(
            user=request.user,
            status=Subscription.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()
        if prof is None or not prof.is_verified or not has_active_sub:
            return Response(
                {"detail": "حذف الرسالة من الطرف الآخر متاح لمشتركي التوثيق فقط."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from common.crypto import sender_fingerprint

        fp = sender_fingerprint(request.user.username)
        message = get_object_or_404(
            Message,
            pk=pk,
            sender_fingerprint=fp,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        message.status = Message.Status.DELETED
        message.deleted_at = tz.now()
        message.save(update_fields=["status", "deleted_at"])
        # Drop its notifications so the bell never points at a dead message.
        Notification.objects.filter(message=message).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class MessageReplyView(APIView):
    """POST /api/messages/<id>/reply/ — the recipient answers a message.

    The reply is stored encrypted (AES-256-GCM) like the body. It becomes
    visible ONLY to the recipient (inbox) and the original sender (sent
    page via fingerprint) — never to the public.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from common.crypto import encrypt_message
        from messages_app.serializers import validate_reply_text

        message = get_object_or_404(
            Message,
            pk=pk,
            recipient=request.user,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        text = validate_reply_text(str(request.data.get("reply", "")))
        if text is None:
            return Response(
                {"detail": "اكتب ردًا من 1 إلى 2000 حرف."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cipher, nonce = encrypt_message(text)
        message.reply_ciphertext = cipher
        message.reply_nonce = nonce
        message.replied_at = timezone.now()
        message.save(update_fields=["reply_ciphertext", "reply_nonce", "replied_at"])
        return Response(
            {"detail": "تم إرسال ردك.", "replied_at": message.replied_at}
        )

class MessageImageView(APIView):
    """GET /api/messages/<id>/image/ — recipient-only attached image.

    لو الصورة على Catbox (image_url) نعيد توجيه آمن للرابط.
    لو ملف محلي قديم نخدمه كما قبل — ثم تُحذف الملفات المحلية تدريجياً.
    404 (not 403) for anything else so message existence is not revealed.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from django.http import HttpResponseRedirect

        message = get_object_or_404(
            Message,
            pk=pk,
            recipient=request.user,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        if message.image_url:
            return HttpResponseRedirect(message.image_url)
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
