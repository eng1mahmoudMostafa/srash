from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from messages_app.models import Message

User = get_user_model()


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class SendMessageTests(TestCase):
    def setUp(self):
        # Never spawn the real push thread in tests: daemon threads cannot
        # see uncommitted test data on SQLite (noisy "table is locked" and
        # flaky). The dedicated PushAlertTests cover push synchronously.
        patcher = mock.patch(
            "messages_app.views._dispatch_push", lambda recipient: None
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        super().setUp()
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

    def setUp(self):
        # LocMemCache مشترك بين الاختبارات؛ نمسحه لتجنب تأثر rate-limit
        # ببقايا اختبارات سابقة (نفس سبب الإصلاح في SendingRegressionTests).
        from django.core.cache import cache

        cache.clear()
        # Silence the real push thread (SQLite "table is locked" noise).
        patcher = mock.patch(
            "messages_app.views._dispatch_push", lambda recipient: None
        )
        self.addCleanup(patcher.stop)
        patcher.start()

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
        # Silence the real push thread (SQLite "table is locked" noise).
        patcher = mock.patch(
            "messages_app.views._dispatch_push", lambda recipient: None
        )
        self.addCleanup(patcher.stop)
        patcher.start()

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
        from unittest import mock

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        recipient = self._recipient()
        self._login_sender()
        buf = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(buf, format="JPEG")
        upload = SimpleUploadedFile(
            "a.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        with mock.patch(
            "common.catbox.upload_to_catbox",
            return_value="https://files.catbox.moe/test123.jpg",
        ):
            resp = self.client.post(
                reverse("messages:send"),
                data={"username": "ahmed", "message": "مع صورة", "image": upload},
                format="multipart",
            )
        self.assertEqual(resp.status_code, 201, resp.data)

        msg = Message.objects.get(recipient=recipient)
        # الصورة الآن رابط Catbox بدل ملف محلي
        self.assertEqual(msg.image_url, "https://files.catbox.moe/test123.jpg")
        self.assertFalse(bool(msg.image))

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

        # The recipient opens it → redirect to Catbox — and last-seen got
        # updated by middleware.
        self.client.force_login(recipient)
        resp = self.client.get(
            reverse("messages:image", kwargs={"pk": msg.pk})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://files.catbox.moe/test123.jpg")
        recipient.refresh_from_db()
        self.assertIsNotNone(recipient.last_seen_at)

        recipient.refresh_from_db()
        self.assertIsNotNone(recipient.last_seen_at)

    def test_image_saved_locally_when_catbox_fails(self):
        """Catbox outage must NOT lose the attachment: the image falls back
        to local storage and stays served via the recipient-only endpoint."""
        import tempfile
        from io import BytesIO
        from unittest import mock

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        recipient = self._recipient()
        self._login_sender()
        buf = BytesIO()
        Image.new("RGB", (32, 32), "red").save(buf, format="JPEG")
        upload = SimpleUploadedFile(
            "b.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                with mock.patch(
                    "common.catbox.upload_to_catbox",
                    side_effect=RuntimeError("تعذر رفع الصورة"),
                ):
                    resp = self.client.post(
                        reverse("messages:send"),
                        data={
                            "username": "ahmed",
                            "message": "صورة محلي",
                            "image": upload,
                        },
                        format="multipart",
                    )
                self.assertEqual(resp.status_code, 201, resp.data)

                msg = Message.objects.get(recipient=recipient)
                self.assertTrue(bool(msg.image))
                self.assertFalse(msg.image_url)

                # The recipient can still open the local fallback file.
                self.client.force_login(recipient)
                resp = self.client.get(
                    reverse("messages:image", kwargs={"pk": msg.pk})
                )
                self.assertEqual(resp.status_code, 200)
                # Consume + close so the file handle doesn't block the
                # TemporaryDirectory cleanup on Windows (WinError 32).
                b"".join(resp.streaming_content)
                resp.close()


class ImgbbFallbackTests(TestCase):
    """لما Catbox يرفض الـ IP (412 من داتا سنتر) ننتقل لـ ImgBB تلقائيًا."""

    def test_uses_imgbb_when_catbox_fails_and_key_set(self):
        import os
        from unittest import mock

        from common import catbox as catbox_mod

        with mock.patch.dict(os.environ, {"IMGBB_KEY": "test-key-123"}):
            with mock.patch.object(
                catbox_mod, "_post_catbox", side_effect=RuntimeError("HTTP Error 412")
            ):
                with mock.patch.object(
                    catbox_mod,
                    "_post_imgbb",
                    return_value="https://i.ibb.co/abc/t.jpg",
                ) as imgbb:
                    with mock.patch("common.catbox.time.sleep"):
                        url = catbox_mod.upload_to_catbox(b"jpegbytes", "t.jpg")
        self.assertEqual(url, "https://i.ibb.co/abc/t.jpg")
        imgbb.assert_called_once_with(b"jpegbytes", "t.jpg")

    def test_raises_without_imgbb_key_so_views_save_locally(self):
        import os
        from unittest import mock

        from common import catbox as catbox_mod

        with mock.patch.dict(os.environ, {"IMGBB_KEY": ""}):
            with mock.patch.object(
                catbox_mod, "_post_catbox", side_effect=RuntimeError("HTTP Error 412")
            ):
                with mock.patch.object(catbox_mod, "_post_imgbb") as imgbb:
                    with mock.patch("common.catbox.time.sleep"):
                        with self.assertRaises(RuntimeError):
                            catbox_mod.upload_to_catbox(b"jpegbytes", "t.jpg")
        imgbb.assert_not_called()


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class AvatarRemoveTests(TestCase):
    """خيار إلغاء الصورة: the owner can delete their account photo."""

    def _upload_avatar(self):
        from io import BytesIO
        from unittest import mock

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = BytesIO()
        Image.new("RGB", (32, 32), "green").save(buf, format="JPEG")
        upload = SimpleUploadedFile(
            "me.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        with mock.patch(
            "common.catbox.upload_to_catbox",
            return_value="https://files.catbox.moe/avatar1.jpg",
        ):
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
        # الأفاتار الآن رابط Catbox بدل ملف محلي
        self.assertEqual(profile.avatar_url, "https://files.catbox.moe/avatar1.jpg")

        resp = self.client.delete(reverse("settings:avatar"))
        self.assertEqual(resp.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.avatar_url)

        # Removing again → 404 (nothing to remove).
        self.assertEqual(
            self.client.delete(reverse("settings:avatar")).status_code, 404
        )

    def test_remove_avatar_requires_login(self):
        self.assertEqual(
            self.client.delete(reverse("settings:avatar")).status_code,
            403,
        )

    def test_avatar_saved_locally_when_catbox_fails(self):
        """Catbox outage must NOT 502 the avatar upload: it falls back to
        local storage (served from /media/) instead of failing."""
        import tempfile
        from io import BytesIO
        from unittest import mock

        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        from users.models import Profile

        me = User.objects.create_user(username="ahmed", password="Secret-12345")
        self.client.force_login(me)
        buf = BytesIO()
        Image.new("RGB", (32, 32), "green").save(buf, format="JPEG")
        upload = SimpleUploadedFile(
            "me.jpg", buf.getvalue(), content_type="image/jpeg"
        )
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                with mock.patch(
                    "common.catbox.upload_to_catbox",
                    side_effect=RuntimeError("تعذر رفع الصورة"),
                ):
                    resp = self.client.post(
                        reverse("settings:avatar"),
                        data={"avatar": upload},
                        format="multipart",
                    )
                self.assertEqual(resp.status_code, 200, resp.data)

                profile = Profile.objects.get(user=me)
                self.assertTrue(bool(profile.avatar))
                self.assertFalse(profile.avatar_url)
                self.assertTrue(resp.data.get("avatar_url"))


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6
)
class InboxPaginationTests(TestCase):
    """page/page_size envelope that powers the SPA's "load more" button."""

    def setUp(self):
        # Rate-limit + session buckets live in cache; isolate each test.
        cache.clear()
        # Silence the real push thread (SQLite "table is locked" noise).
        patcher = mock.patch(
            "messages_app.views._dispatch_push", lambda recipient: None
        )
        self.addCleanup(patcher.stop)
        patcher.start()
        self.recipient = User.objects.create_user(
            username="ahmed", password="Secret-12345"
        )
        self.sender = User.objects.create_user(
            username="sara", password="Secret-12345"
        )
        self.client.force_login(self.sender)
        for i in range(3):
            resp = self.client.post(
                reverse("messages:send"),
                data={"username": "ahmed", "message": f"رسالة رقم {i}"},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 201, resp.data)
        self.client.logout()

    def test_inbox_pages_and_flags(self):
        self.client.force_login(self.recipient)
        page1 = self.client.get(
            reverse("messages:inbox"), {"page": 1, "page_size": 2}
        )
        self.assertEqual(page1.status_code, 200)
        self.assertEqual(page1.data["page"], 1)
        self.assertEqual(page1.data["total"], 3)
        self.assertEqual(len(page1.data["results"]), 2)
        self.assertTrue(page1.data["has_next"])
        self.assertFalse(page1.data["has_prev"])

        page2 = self.client.get(
            reverse("messages:inbox"), {"page": 2, "page_size": 2}
        )
        self.assertEqual(len(page2.data["results"]), 1)
        self.assertFalse(page2.data["has_next"])
        self.assertTrue(page2.data["has_prev"])

    def test_invalid_page_param_falls_back_to_first(self):
        self.client.force_login(self.recipient)
        resp = self.client.get(reverse("messages:inbox"), {"page": "abc"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(resp.data["total"], 3)

    def test_sent_page_envelope(self):
        self.client.force_login(self.sender)
        resp = self.client.get(
            reverse("messages:sent"), {"page": 1, "page_size": 2}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 3)
        self.assertEqual(len(resp.data["results"]), 2)
        self.assertTrue(resp.data["has_next"])
