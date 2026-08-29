from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from messages_app.models import Message

User = get_user_model()


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class SendMessageTests(TestCase):
    def _login_sender(self, username="sara"):
        """Sending now requires a registered, logged-in account."""
        User.objects.create_user(username=username, password="Secret-12345")
        self.client.post(
            reverse("auth:login"),
            data={"username": username, "password": "Secret-12345"},
            content_type="application/json",
        )

    def test_visitor_cannot_send_without_account(self):
        recipient = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "بصراحة أنت رائع!"},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, (401, 403))
        self.assertFalse(Message.objects.filter(recipient=recipient).exists())

    def test_logged_in_user_can_send(self):
        recipient = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        self._login_sender()
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "بصراحة أنت رائع!"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Message.objects.filter(recipient=recipient).exists())
        # Encrypted at rest; no plaintext, no sender FK, no IP.
        msg = Message.objects.get(recipient=recipient)
        self.assertNotIn("رائع", msg.body_ciphertext)

    def test_cannot_message_yourself(self):
        me = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        self.client.force_login(me)
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "لنفسي"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Message.objects.filter(recipient=me).exists())

    def test_recipient_inbox_and_read(self):
        User.objects.create_user(username="ahmed", password="Secret-12345")
        self._login_sender()
        self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "مرحبا"},
            content_type="application/json",
        )
        self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )
        inbox = self.client.get(reverse("messages:inbox"))
        self.assertEqual(inbox.status_code, 200)
        payload = inbox.data["results"][0]
        self.assertEqual(payload["message"], "مرحبا")
        self.assertFalse(payload["is_read"])

        detail = self.client.patch(
            reverse("messages:detail", kwargs={"pk": payload["id"]})
        )
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.data["is_read"])

    def test_soft_delete_hides_message(self):
        recipient = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        self._login_sender()
        self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "احذفني"},
            content_type="application/json",
        )
        msg = Message.objects.get(recipient=recipient)
        self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )
        resp = self.client.delete(
            reverse("messages:detail", kwargs={"pk": msg.pk})
        )
        self.assertEqual(resp.status_code, 204)
        msg.refresh_from_db()
        self.assertEqual(msg.status, Message.Status.DELETED)
        self.assertIsNotNone(msg.deleted_at)

    def test_blocked_recipient_rejects_message(self):
        User.objects.create_user(
            username="ahmed", password="Secret-12345", accept_anonymous=False
        )
        self._login_sender()
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "ممنوع"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_unknown_recipient_rejected(self):
        self._login_sender()
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "nobody", "message": "من أنت؟"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class SenderRevealTests(TestCase):
    """The optional sender-chosen name is revealed ONLY to recipients with
    an active premium (توثيق) subscription."""

    def _send(self):
        User.objects.create_user(username="sara", password="Secret-12345")
        self.client.post(
            reverse("auth:login"),
            data={"username": "sara", "password": "Secret-12345"},
            content_type="application/json",
        )
        return self.client.post(
            reverse("messages:send"),
            data={
                "username": "ahmed",
                "message": "بصراحة أنت رائع!",
                "sender_name": "محمود مصطفى",
            },
            content_type="application/json",
        )

    def _login_recipient(self):
        self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )

    def test_sender_name_hidden_without_subscription(self):
        User.objects.create_user(username="ahmed", password="Secret-12345")
        self.assertEqual(self._send().status_code, 201)
        self._login_recipient()
        payload = self.client.get(reverse("messages:inbox")).data["results"][0]
        self.assertTrue(payload["has_sender_name"])
        self.assertIsNone(payload["sender_name"])
        # The username is stored (encrypted) but NOT revealed either.
        self.assertTrue(payload["has_sender_username"])
        self.assertIsNone(payload["sender_username"])

    def test_sender_reveal_includes_username_with_active_subscription(self):
        from users.models import Subscription

        recipient = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        self.assertEqual(self._send().status_code, 201)
        sub = Subscription.objects.create(user=recipient)
        sub.activate()  # sets status=active + profile.is_verified=True
        self._login_recipient()
        payload = self.client.get(reverse("messages:inbox")).data["results"][0]
        self.assertEqual(payload["sender_name"], "محمود مصطفى")
        self.assertEqual(payload["sender_username"], "sara")

    def test_invalid_sender_name_rejected(self):
        User.objects.create_user(username="ahmed", password="Secret-12345")
        User.objects.create_user(username="sara", password="Secret-12345")
        self.client.post(
            reverse("auth:login"),
            data={"username": "sara", "password": "Secret-12345"},
            content_type="application/json",
        )
        resp = self.client.post(
            reverse("messages:send"),
            data={
                "username": "ahmed",
                "message": "مرحبا",
                "sender_name": "abc123!!",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class SendingRegressionTests(TestCase):
    """Regression tests for real-world sending failures."""

    def setUp(self):
        # LocMemCache is shared across the whole test run; a previous test's
        # last-seen throttle key (same pk) would suppress the middleware
        # update and make these tests order-dependent/flaky.
        from django.core.cache import cache

        cache.clear()

    def _recipient(self):
        return User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )

    def _login_sender(self):
        User.objects.create_user(username="sara", password="Secret-12345")
        self.client.post(
            reverse("auth:login"),
            data={"username": "sara", "password": "Secret-12345"},
            content_type="application/json",
        )

    def test_blank_or_missing_sender_name_is_accepted(self):
        """The UI always sends sender_name:'' when the visitor leaves it
        empty — it must NOT cause a 400 (this broke sending before)."""
        self._recipient()
        self._login_sender()
        for payload in (
            {"username": "ahmed", "message": "بدون اسم إطلاقًا"},
            {"username": "ahmed", "message": "مع اسم فارغ", "sender_name": ""},
        ):
            resp = self.client.post(
                reverse("messages:send"),
                data=payload,
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 201, resp.data)

    def test_image_attach_open_and_privacy(self):
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        recipient = self._recipient()
        self._login_sender()
        buf = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(buf, format="JPEG")
        upload = SimpleUploadedFile(
            "a.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "مع صورة", "image": upload},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        msg = Message.objects.get(recipient=recipient)
        self.assertTrue(msg.image)

        # Another account can NOT open the image (recipient-only).
        User.objects.create_user(username="omar", password="Secret-12345")
        self.client.post(
            reverse("auth:login"),
            data={"username": "omar", "password": "Secret-12345"},
            content_type="application/json",
        )
        self.assertEqual(
            self.client.get(
                reverse("messages:image", kwargs={"pk": msg.pk})
            ).status_code,
            404,
        )

        # The recipient opens it — and last-seen got updated by middleware.
        self.client.force_login(recipient)
        resp = self.client.get(
            reverse("messages:image", kwargs={"pk": msg.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/jpeg")
        recipient.refresh_from_db()
        self.assertIsNotNone(recipient.last_seen_at)
        img_resp = self.client.get(
            reverse("messages:image", kwargs={"pk": msg.pk})
        )
        self.assertEqual(img_resp.status_code, 200)
        self.assertEqual(img_resp["Content-Type"], "image/jpeg")

        recipient.refresh_from_db()
        self.assertIsNotNone(recipient.last_seen_at)


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class AvatarRemoveTests(TestCase):
    """خيار إلغاء الصورة: the owner can delete their account photo."""

    def _upload_avatar(self):
        from io import BytesIO

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = BytesIO()
        Image.new("RGB", (32, 32), "green").save(buf, format="JPEG")
        upload = SimpleUploadedFile(
            "me.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        return self.client.post(
            reverse("settings:avatar"),
            data={"avatar": upload},
            format="multipart",
        )

    def test_owner_can_remove_avatar(self):
        me = User.objects.create_user(username="ahmed", password="Secret-12345")
        self.client.force_login(me)
        self.assertEqual(self._upload_avatar().status_code, 200)

        from users.models import Profile

        profile = Profile.objects.get(user=me)
        self.assertTrue(profile.avatar)

        resp = self.client.delete(reverse("settings:avatar"))
        self.assertEqual(resp.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.avatar)

        # Removing again → 404 (nothing to remove).
        self.assertEqual(
            self.client.delete(reverse("settings:avatar")).status_code, 404
        )

    def test_remove_avatar_requires_login(self):
        self.assertEqual(
            self.client.delete(reverse("settings:avatar")).status_code,
            403,
        )
