from django.test import TestCase

from common.crypto import decrypt_message, encrypt_message, sign_ip
from common.spam import score_message, should_auto_flag


class CryptoTests(TestCase):
    def test_roundtrip(self):
        ciphertext, nonce = encrypt_message("بصراحة أنت رائع!")
        self.assertNotIn("رائع", ciphertext)  # not plaintext in storage
        self.assertEqual(decrypt_message(ciphertext, nonce), "بصراحة أنت رائع!")

    def test_sign_ip_is_one_way_and_stable(self):
        ip = "203.0.113.9"
        sig = sign_ip(ip)
        self.assertNotEqual(sig, ip)
        self.assertEqual(sig, sign_ip(ip))


class SpamTests(TestCase):
    def test_low_risk_message_scores_low(self):
        self.assertLess(score_message("أحب الأخوة في الله"), 60)
        self.assertFalse(should_auto_flag("أحب الأخوة في الله"))

    def test_link_and_win_flags(self):
        self.assertTrue(should_auto_flag("اضغط على www.free-prize.net واربح الهدية"))
        self.assertGreater(score_message("a" * 40), 0)