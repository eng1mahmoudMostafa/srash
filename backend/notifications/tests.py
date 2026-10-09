from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from messages_app.models import Message
from notifications.models import Notification

User = get_user_model()


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class NotificationFlowTests(TestCase):
    """The bell badge: created on delivery, kept in sync with read/delete."""

    def setUp(self):
        # Rate-limit + session buckets live in cache; isolate each test.
        cache.clear()
        # Silence the real push thread (SQLite "table is locked" noise).
        patcher = mock.patch(
            "messages_app.views._dispatch_push", lambda recipient: None
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.alice = User.objects.create_user(
            username="alice", password="Secret-12345"
        )
        self.bob = User.objects.create_user(
            username="bob", password="Secret-12345"
        )

    def _send(self, text="إشعار"):
        self.client.force_login(self.alice)
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "bob", "message": text},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.client.logout()

    def test_send_creates_notification(self):
        self._send()
        note = Notification.objects.get(recipient=self.bob)
        self.assertEqual(note.kind, "new_message")
        self.assertFalse(note.is_read)

    def test_list_returns_unread_count(self):
        self._send()
        self.client.force_login(self.bob)
        data = self.client.get(reverse("notifications:list")).data
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["unread"], 1)

    def test_mark_one_read_and_read_all(self):
        self._send("واحدة")
        self._send("اثنتان")
        self.client.force_login(self.bob)
        first = self.client.get(reverse("notifications:list")).data["results"][0]
        resp = self.client.post(
            reverse("notifications:read", kwargs={"pk": first["id"]})
        )
        self.assertEqual(resp.data["unread"], 1)
        resp = self.client.post(reverse("notifications:read-all"))
        self.assertEqual(resp.data["unread"], 0)

    def test_reading_message_clears_its_notification(self):
        self._send()
        note = Notification.objects.get(recipient=self.bob)
        self.client.force_login(self.bob)
        resp = self.client.patch(
            reverse("messages:detail", kwargs={"pk": note.message_id})
        )
        self.assertEqual(resp.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_deleting_message_removes_notification(self):
        self._send()
        note = Notification.objects.get(recipient=self.bob)
        self.client.force_login(self.bob)
        resp = self.client.delete(
            reverse("messages:detail", kwargs={"pk": note.message_id})
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Notification.objects.filter(pk=note.pk).exists())

    def test_cannot_mark_others_notification(self):
        self._send()
        note = Notification.objects.get(recipient=self.bob)
        # alice is not the recipient: the filter must leave it untouched.
        self.client.force_login(self.alice)
        resp = self.client.post(
            reverse("notifications:read", kwargs={"pk": note.pk})
        )
        self.assertEqual(resp.status_code, 200)
        note.refresh_from_db()
        self.assertFalse(note.is_read)
