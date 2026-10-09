"""Auth, registration, security-question recovery and push endpoints."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

# Registration always carries these two required fields.
SECURITY_Q = "ما اسم مدرستي الابتدائية؟"
SECURITY_A = "النور"


def register_payload(**over):
    data = {
        "username": "ahmed",
        "password": "Secret-12345",
        "full_name": "احمد محمود",
        "security_question": SECURITY_Q,
        "security_answer": SECURITY_A,
    }
    data.update(over)
    return data


class AuthFlowTests(TestCase):
    def test_register_login_logout_me(self):
        reg = self.client.post(
            reverse("auth:register"),
            data=register_payload(),
            content_type="application/json",
        )
        self.assertEqual(reg.status_code, 201)
        self.assertTrue(User.objects.filter(username="ahmed").exists())
        # The real name seeds the public profile display name.
        from users.models import Profile

        self.assertEqual(
            Profile.objects.get(user__username="ahmed").display_name,
            "احمد محمود",
        )

        me = self.client.get(reverse("auth:me"))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "ahmed")
        self.assertIn("/u/ahmed", me.data["shareable_url"])

        logout = self.client.post(reverse("auth:logout"))
        self.assertEqual(logout.status_code, 204)
        self.assertIn(
            self.client.get(reverse("auth:me")).status_code, (401, 403)
        )

        login = self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_register_stores_a_hashed_security_answer(self):
        """The answer must be verifiable but never stored in plaintext."""
        self.client.post(
            reverse("auth:register"),
            data=register_payload(username="sara", full_name="سارة علي"),
            content_type="application/json",
        )
        user = User.objects.get(username="sara")
        self.assertEqual(user.security_question, SECURITY_Q)
        self.assertNotIn(SECURITY_A, user.security_answer_hash)
        self.assertTrue(user.check_security_answer(SECURITY_A))
        self.assertFalse(user.check_security_answer("اجابة اخرى"))

    def test_security_answer_ignores_arabic_spelling_variants(self):
        """Alef/yeh differences must not lock the owner out."""
        self.client.post(
            reverse("auth:register"),
            data=register_payload(
                username="var",
                full_name="سارة علي",
                security_answer="احمد",
            ),
            content_type="application/json",
        )
        user = User.objects.get(username="var")
        self.assertTrue(user.check_security_answer("احمد"))
        self.assertTrue(user.check_security_answer("  احمد  "))

    def test_register_requires_security_question(self):
        for field in ("security_question", "security_answer"):
            resp = self.client.post(
                reverse("auth:register"),
                data=register_payload(username="q1", **{field: ""}),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 400, field)
            self.assertIn(field, resp.data)
        self.assertFalse(User.objects.filter(username="q1").exists())

    def test_register_requires_real_name(self):
        resp = self.client.post(
            reverse("auth:register"),
            data=register_payload(username="n1", full_name=""),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        for bad in ("", "محمود", "abc123!!"):
            resp = self.client.post(
                reverse("auth:register"),
                data=register_payload(username="n2", full_name=bad),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 400, bad)
        self.assertFalse(User.objects.filter(username__in=["n1", "n2"]).exists())

    def test_register_password_errors_are_arabic(self):
        resp = self.client.post(
            reverse("auth:register"),
            data=register_payload(username="n3", password="123"),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("This password is too short", str(resp.data))


class PublicProfileTests(TestCase):
    def test_public_profile_lookup(self):
        User.objects.create_user(username="mahmoud", password="Secret-12345")
        url = reverse("users:public-profile", kwargs={"username": "mahmoud"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["username"], "mahmoud")

    def test_missing_profile_returns_404(self):
        url = reverse("users:public-profile", kwargs={"username": "nobody"})
        self.assertEqual(self.client.get(url).status_code, 404)


@override_settings(RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6)
class PasswordRecoveryTests(TestCase):
    """Password recovery by the account's own question — no e-mail at all."""

    def setUp(self):
        cache.clear()
        self.client.post(
            reverse("auth:register"),
            data=register_payload(username="mona", full_name="منى سعيد"),
            content_type="application/json",
        )
        self.user = User.objects.get(username="mona")

    def test_recovery_start_returns_the_question(self):
        resp = self.client.post(
            reverse("auth:recovery"),
            data={"username": "mona"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["recoverable"])
        self.assertEqual(resp.data["security_question"], SECURITY_Q)

    def test_recovery_start_is_enumeration_safe(self):
        """Unknown usernames get the exact same body as known ones."""
        known = self.client.post(
            reverse("auth:recovery"),
            data={"username": "mona"},
            content_type="application/json",
        )
        unknown = self.client.post(
            reverse("auth:recovery"),
            data={"username": "ghost"},
            content_type="application/json",
        )
        self.assertEqual(unknown.status_code, 200)
        # A probe cannot tell an existing account from a missing one.
        self.assertEqual(set(unknown.data.keys()), set(known.data.keys()))
        self.assertFalse(unknown.data["recoverable"])
        self.assertEqual(unknown.data["security_question"], "")

    def test_correct_answer_sets_a_new_password(self):
        resp = self.client.post(
            reverse("auth:recovery-confirm"),
            data={
                "username": "mona",
                "security_answer": SECURITY_A,
                "new_password": "FreshPass-77",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("FreshPass-77"))
        login = self.client.post(
            reverse("auth:login"),
            data={"username": "mona", "password": "FreshPass-77"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_wrong_answer_is_rejected_and_changes_nothing(self):
        resp = self.client.post(
            reverse("auth:recovery-confirm"),
            data={
                "username": "mona",
                "security_answer": "اجابة خاطئة",
                "new_password": "FreshPass-77",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Secret-12345"))

    def test_unknown_username_gets_the_same_error(self):
        wrong = self.client.post(
            reverse("auth:recovery-confirm"),
            data={
                "username": "mona",
                "security_answer": "x",
                "new_password": "FreshPass-77",
            },
            content_type="application/json",
        )
        ghost = self.client.post(
            reverse("auth:recovery-confirm"),
            data={
                "username": "ghost",
                "security_answer": "x",
                "new_password": "FreshPass-77",
            },
            content_type="application/json",
        )
        self.assertEqual(str(ghost.data), str(wrong.data))

    def test_account_without_a_question_is_not_recoverable(self):
        User.objects.create_user(username="bare", password="Secret-12345")
        resp = self.client.post(
            reverse("auth:recovery"),
            data={"username": "bare"},
            content_type="application/json",
        )
        self.assertFalse(resp.data["recoverable"])


@override_settings(RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6)
class PushAlertTests(TestCase):
    """A new message raises the bell and pushes to subscribed devices."""

    def _subscribe(self, owner):
        from notifications.models import PushSubscription
        from users.models import UserSettings

        # الصف مطلوب: خيط الإشعارات يقرأه (وفي بيئة الاختبار قد يفشل إنشاؤه
        # من الخيط بسبب قفل قاعدة البيانات) — أنشئه هنا مسبقًا.
        UserSettings.objects.get_or_create(user=owner)
        self.client.force_login(owner)
        self.client.post(
            reverse("notifications:push-subscribe"),
            data={
                "endpoint": "https://push.example.com/abc",
                "keys": {"p256dh": "A" * 43, "auth": "B" * 22},
            },
            content_type="application/json",
        )
        return PushSubscription.objects.get(user=owner)

    def test_public_key_endpoint_reports_availability(self):
        resp = self.client.get(reverse("notifications:push-key"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("enabled", resp.data)

    def test_subscribe_requires_valid_keys(self):
        owner = User.objects.create_user(username="rec", password="Secret-12345")
        self.client.force_login(owner)
        resp = self.client.post(
            reverse("notifications:push-subscribe"),
            data={"endpoint": "https://push.example.com/x", "keys": {}},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_unsubscribe_drops_the_device(self):
        from notifications.models import PushSubscription

        owner = User.objects.create_user(username="rec", password="Secret-12345")
        sub = self._subscribe(owner)
        self.assertTrue(PushSubscription.objects.filter(pk=sub.pk).exists())
        self.client.post(
            reverse("notifications:push-unsubscribe"),
            data={"endpoint": "https://push.example.com/abc"},
            content_type="application/json",
        )
        self.assertFalse(PushSubscription.objects.filter(pk=sub.pk).exists())

    def _send_without_push(self, data):
        """POST messages:send with the background push disabled."""
        import messages_app.views as send_views

        with patch.object(send_views, "_dispatch_push", lambda recipient: None):
            return self.client.post(
                reverse("messages:send"),
                data=data,
                content_type="application/json",
            )

    def test_new_message_creates_in_app_notification(self):
        from notifications.models import Notification

        User.objects.create_user(username="rec", password="Secret-12345")
        self.client.post(
            reverse("auth:register"),
            data=register_payload(username="sender"),
            content_type="application/json",
        )
        resp = self._send_without_push(
            {"username": "rec", "message": "بصراحة أنت رائع!"}
        )
        self.assertEqual(resp.status_code, 201)
        note = Notification.objects.get(recipient__username="rec")
        self.assertEqual(note.kind, "new_message")
        self.assertFalse(note.is_read)

    def test_push_fires_without_the_message_body(self):
        """The push payload never carries the message text or the sender."""
        import messages_app.views as send_views
        from common import push as push_module

        owner = User.objects.create_user(username="rec", password="Secret-12345")
        self._subscribe(owner)

        sent = []

        def fake_send(subscription, payload):
            sent.append((subscription, payload))
            return True

        # Run the push synchronously inside the test transaction: daemon
        # threads cannot see uncommitted test data on SQLite, so waiting on
        # a real thread here is flaky (often "database table is locked").
        with (
            patch.object(push_module, "send_push", side_effect=fake_send),
            patch.object(push_module, "is_configured", return_value=True),
            patch.object(
                send_views,
                "_dispatch_push",
                side_effect=lambda recipient: send_views._push_async(recipient),
            ),
        ):
            sender = User.objects.create_user(
                username="sender", password="Secret-12345"
            )
            self.client.force_login(sender)
            resp = self.client.post(
                reverse("messages:send"),
                data={"username": "rec", "message": "سر لا يعرفه أحد"},
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 201)

        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1]["body"], "لديك رسالة مجهولة جديدة 📩")
        self.assertNotIn("سر لا يعرفه أحد", str(sent[0][1]))

    def test_push_switch_off_silences_every_device(self):
        from common import push as push_module
        from users.models import UserSettings

        owner = User.objects.create_user(username="rec", password="Secret-12345")
        self._subscribe(owner)
        UserSettings.objects.filter(user=owner).update(push_notifications=False)

        called = []
        original = push_module.send_push
        original_ok = push_module.is_configured
        push_module.send_push = lambda *a, **k: called.append(a) or True
        push_module.is_configured = lambda: True
        try:
            self.assertEqual(push_module.notify_new_message(owner), 0)
        finally:
            push_module.send_push = original
            push_module.is_configured = original_ok
        self.assertFalse(called)

    def test_account_missing_a_settings_row_still_gets_alerts(self):
        """get_or_create: pre-existing accounts default to alerts ON."""
        from common import push as push_module
        from notifications.models import PushSubscription
        from users.models import UserSettings

        owner = User.objects.create_user(username="rec", password="Secret-12345")
        PushSubscription.objects.create(
            user=owner,
            endpoint="https://push.example.com/abc",
            p256dh="k",
            auth="a",
        )
        self.assertFalse(UserSettings.objects.filter(user=owner).exists())

        sent = []
        original = push_module.send_push
        original_ok = push_module.is_configured
        push_module.send_push = lambda sub, payload: sent.append(payload) or True
        push_module.is_configured = lambda: True
        try:
            self.assertEqual(push_module.notify_new_message(owner), 1)
        finally:
            push_module.send_push = original
            push_module.is_configured = original_ok
        self.assertTrue(UserSettings.objects.filter(user=owner).exists())


@override_settings(RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6)
class ToggleAnonymousTests(TestCase):
    """Pausing anonymous messages must block senders until re-enabled."""

    def test_toggle_off_and_back_on(self):
        me = User.objects.create_user(username="ahmed", password="Secret-12345")
        User.objects.create_user(username="sara", password="Secret-12345")
        self.client.force_login(me)

        self.assertTrue(me.accept_anonymous)
        self.assertTrue(
            self.client.get(reverse("auth:me")).data["accept_anonymous"]
        )

        r = self.client.post(reverse("settings:toggle-anonymous"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["accept_anonymous"])
        me.refresh_from_db()
        self.assertFalse(me.accept_anonymous)

        self.client.force_login(User.objects.get(username="sara"))
        denied = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "مرحبا"},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(me)
        r = self.client.post(reverse("settings:toggle-anonymous"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["accept_anonymous"])
