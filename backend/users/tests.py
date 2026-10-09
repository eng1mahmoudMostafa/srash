from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from common.mail import PASSWORD_RESET_SALT

User = get_user_model()


class AuthFlowTests(TestCase):
    def test_register_login_logout_me(self):
        reg = self.client.post(
            reverse("auth:register"),
            data={
                "username": "ahmed",
                "password": "Secret-12345",
                "full_name": "أحمد محمود",
            },
            content_type="application/json",
        )
        self.assertEqual(reg.status_code, 201)
        self.assertTrue(User.objects.filter(username="ahmed").exists())
        # The real name seeds the public profile display name.
        from users.models import Profile

        self.assertEqual(
            Profile.objects.get(user__username="ahmed").display_name,
            "أحمد محمود",
        )

        me = self.client.get(reverse("auth:me"))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "ahmed")
        self.assertIn("/u/ahmed", me.data["shareable_url"])

        logout = self.client.post(reverse("auth:logout"))
        self.assertEqual(logout.status_code, 204)
        # After logout the session is gone; expect 401 or 403 (no auth).
        self.assertIn(self.client.get(reverse("auth:me")).status_code, (401, 403))

        login = self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200)

    def test_register_without_email_is_allowed(self):
        resp = self.client.post(
            reverse("auth:register"),
            data={
                "username": "sara",
                "password": "Secret-12345",
                "full_name": "سارة علي",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_register_requires_real_name(self):
        # Missing name → rejected.
        resp = self.client.post(
            reverse("auth:register"),
            data={"username": "n1", "password": "Secret-12345"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # Blank / digits-only name → rejected.
        for bad in ("", "محمود", "abc123!!"):
            resp = self.client.post(
                reverse("auth:register"),
                data={
                    "username": "n2",
                    "password": "Secret-12345",
                    "full_name": bad,
                },
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 400, bad)
        self.assertFalse(User.objects.filter(username__in=["n1", "n2"]).exists())

    def test_register_password_errors_are_arabic(self):
        resp = self.client.post(
            reverse("auth:register"),
            data={
                "username": "n3",
                "password": "123",
                "full_name": "محمود مصطفى",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        text = str(resp.data)
        self.assertNotIn("This password is too short", text)


class PublicProfileTests(TestCase):
    def test_public_profile_lookup(self):
        user = User.objects.create_user(username="mahmoud", password="Secret-12345")
        url = reverse("users:public-profile", kwargs={"username": "mahmoud"})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["username"], "mahmoud")

    def test_missing_profile_returns_404(self):
        url = reverse("users:public-profile", kwargs={"username": "nobody"})
        self.assertEqual(self.client.get(url).status_code, 404)


@override_settings(
    RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailNotificationTest(TestCase):
    """A linked, verified e-mail receives a privacy-safe new-message alert."""

    def test_new_message_sends_notification(self):
        from django.core import mail

        User.objects.create_user(username="rec", password="Secret-12345",
                                 email="rec@example.com", email_verified=True)
        # notify_new_message is ON by default now; be explicit anyway.
        from users.models import UserSettings

        us = UserSettings.objects.get_or_create(
            user=User.objects.get(username="rec"))[0]
        us.notify_new_message = True
        us.save()

        # The sender must be a logged-in account.
        self.client.post(
            reverse("auth:register"),
            data={"username": "sender", "password": "Secret-12345",
                  "full_name": "محمود مصطفى"},
            content_type="application/json",
        )
        resp = self.client.post(
            reverse("messages:send"),
            data={"username": "rec", "message": "بصراحة أنت رائع!"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("رسالة جديدة", mail.outbox[0].subject)
        # Privacy: the mail never contains the message body.
        self.assertNotIn("بصراحة أنت رائع!", mail.outbox[0].body)


@override_settings(RATE_LIMIT_PER_MINUTE=10**6, RATE_LIMIT_PER_HOUR=10**6)
class ToggleAnonymousTests(TestCase):
    """إيقاف استقبال الرسائل ثم إعادة تفعيله يجب أن يعمل ذهاباً وإياباً."""

    def test_toggle_off_and_back_on(self):
        me = User.objects.create_user(username="ahmed", password="Secret-12345")
        User.objects.create_user(username="sara", password="Secret-12345")
        self.client.force_login(me)

        # الحالة الافتراضية: يستقبل
        self.assertTrue(me.accept_anonymous)
        # /me ترجع الحالة للواجهة
        self.assertTrue(self.client.get(reverse("auth:me")).data["accept_anonymous"])

        # 1) إيقاف
        r = self.client.post(reverse("settings:toggle-anonymous"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["accept_anonymous"])
        me.refresh_from_db()
        self.assertFalse(me.accept_anonymous)

        # المرسل يُرفض أثناء الإيقاف
        self.client.force_login(User.objects.get(username="sara"))
        denied = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "مرحبا"},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 403)

        # 2) إعادة التفعيل — وهنا كانت المشكلة
        self.client.force_login(me)
        r = self.client.post(reverse("settings:toggle-anonymous"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["accept_anonymous"])
        me.refresh_from_db()
        self.assertTrue(me.accept_anonymous)

        # المرسل يُقبل بعد إعادة التفعيل
        self.client.force_login(User.objects.get(username="sara"))
        ok = self.client.post(
            reverse("messages:send"),
            data={"username": "ahmed", "message": "مرحبا مجدداً"},
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 201)

    def test_privacy_checkbox_and_toggle_stay_in_sync(self):
        """checkbox الخصوصية وزر الاستقبال نظام واحد موحّد (لا تعارض)."""
        from users.models import UserSettings

        u = User.objects.create_user(username="mona", password="Secret-12345")
        self.client.force_login(u)

        # 1) إلغاء checkbox "السماح باستقبال الرسائل المجهولة" وحفظه
        r = self.client.patch(
            reverse("settings:settings"),
            data={"allow_anonymous": False},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["allow_anonymous"])
        u.refresh_from_db()
        # المزامنة: الحقل الفعلي accept_anonymous (الذي يفحصه الإرسال) صار False
        self.assertFalse(u.accept_anonymous)
        # والواجهة تعرض الحالة نفسها
        self.assertFalse(
            self.client.get(reverse("auth:me")).data["accept_anonymous"]
        )

        # 2) زر التبديل يعكس القيمة ويُزامن checkbox معه
        r = self.client.post(reverse("settings:toggle-anonymous"))
        self.assertTrue(r.data["accept_anonymous"])
        u.refresh_from_db()
        self.assertTrue(u.accept_anonymous)
        us = UserSettings.objects.get(user=u)
        self.assertTrue(us.allow_anonymous)  # checkbox تبع الزر فوراً
        self.assertTrue(
            self.client.get(reverse("settings:settings")).data[
                "allow_anonymous"
            ]
        )


class PasswordChangeTests(TestCase):
    def setUp(self):
        # Rate-limit + session buckets live in cache; isolate each test.
        cache.clear()
        self.user = User.objects.create_user(
            username="ahmed",
            password="Secret-12345",
            email="ahmed@example.com",
        )
        self.client.force_login(self.user)

    def test_change_password_requires_correct_old_one(self):
        bad = self.client.post(
            reverse("auth:change-password"),
            data={
                "old_password": "Wrong-99999",
                "new_password": "NewPass-9876",
            },
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Secret-12345"))

    def test_change_password_success_keeps_own_session(self):
        ok = self.client.post(
            reverse("auth:change-password"),
            data={
                "old_password": "Secret-12345",
                "new_password": "NewPass-9876",
            },
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200, ok.data)
        # Same session survives (update_session_auth_hash)...
        self.assertEqual(self.client.get(reverse("auth:me")).status_code, 200)
        # ...but only the new password logs in from now on.
        self.client.post(reverse("auth:logout"))
        old = self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "Secret-12345"},
            content_type="application/json",
        )
        self.assertIn(old.status_code, (400, 401, 403))
        new = self.client.post(
            reverse("auth:login"),
            data={"username": "ahmed", "password": "NewPass-9876"},
            content_type="application/json",
        )
        self.assertEqual(new.status_code, 200)

    def test_change_password_rejects_new_equal_to_old(self):
        resp = self.client.post(
            reverse("auth:change-password"),
            data={
                "old_password": "Secret-12345",
                "new_password": "Secret-12345",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="mona",
            password="Secret-12345",
            email="mona@example.com",
        )

    def test_forgot_password_is_enumeration_safe(self):
        known = self.client.post(
            reverse("auth:forgot-password"),
            data={"email": "mona@example.com"},
            content_type="application/json",
        )
        self.assertEqual(known.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/reset-password?t=", mail.outbox[0].body)

        unknown = self.client.post(
            reverse("auth:forgot-password"),
            data={"email": "nobody@example.com"},
            content_type="application/json",
        )
        self.assertEqual(unknown.status_code, 200)
        # Same body either way — probing addresses reveals nothing.
        self.assertEqual(unknown.data["detail"], known.data["detail"])
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_confirm_sets_new_password(self):
        token = signing.dumps({"uid": self.user.pk}, salt=PASSWORD_RESET_SALT)
        resp = self.client.post(
            reverse("auth:reset-password"),
            data={"t": token, "new_password": "FreshPass-77"},
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

    def test_invalid_reset_token_rejected(self):
        resp = self.client.post(
            reverse("auth:reset-password"),
            data={"t": "garbage-token", "new_password": "FreshPass-77"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Secret-12345"))
