from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from messages_app.models import Message
from moderation.models import Report

User = get_user_model()


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class ReportTests(TestCase):
    def _send_to(self, target, message):
        """Sending requires a logged-in sender account."""
        User.objects.create_user(username="sara", password="Secret-12345")
        self.client.post(
            reverse("auth:login"),
            data={"username": "sara", "password": "Secret-12345"},
            content_type="application/json",
        )
        return self.client.post(
            reverse("messages:send"),
            data={"username": target, "message": message},
            content_type="application/json",
        )

    def test_recipient_can_report_message(self):
        recipient = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        self._send_to("ahmed", "رسالة مزعجة")
        msg = Message.objects.get(recipient=recipient)
        self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )
        resp = self.client.post(
            reverse("messages:report", kwargs={"message_id": msg.pk}),
            data={"reason": "spam", "note": "رسالة إعلانية"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Report.objects.filter(message=msg).exists())

    def test_cannot_report_others_message(self):
        other = User.objects.create_user(
            username="other", password="Secret-12345"
        )
        User.objects.create_user(username="ahmed", password="Secret-12345")
        self._send_to("ahmed", "ليست لك")
        msg = Message.objects.get(recipient__username="ahmed")
        self.client.post(
            reverse("auth:login"),
            data={"username": "other", "password": "Secret-12345"},
            content_type="application/json",
        )
        resp = self.client.post(
            reverse("messages:report", kwargs={"message_id": msg.pk}),
            data={"reason": "spam"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)