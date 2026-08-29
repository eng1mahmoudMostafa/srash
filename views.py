from rest_framework import permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from messages_app.models import Message
from moderation.serializers import ReportSerializer


class CreateReportView(APIView):
    """POST /api/messages/<id>/report — recipient reports a received message."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, message_id):
        message = get_object_or_404(
            Message,
            pk=message_id,
            recipient=request.user,
            status__in=[Message.Status.ACTIVE, Message.Status.FLAGGED],
        )
        serializer = ReportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(
            message_obj=message,
            reporter_obj=request.user,
        )
        return Response(
            {"success": True, "message": "تم إرسال البلاغ. شكرًا لك."},
            status=status.HTTP_201_CREATED,
        )