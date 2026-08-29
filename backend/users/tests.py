from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

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