"""Web Push delivery (VAPID) — no e-mail, no third-party account needed.

A push is sent straight from this server to the browser's push service
(Google's FCM for Chrome/Android, Mozilla's for Firefox, Apple's for iOS).
The payload is end-to-end encrypted by the *browser* using the keys it
handed us at subscribe time, so we can never read our own notification and
neither can the push service: only "you have a new message".

Everything here fails soft: an unreachable push service, a revoked
subscription (410 Gone) or a missing VAPID key must never break the request
that triggered it. The in-app bell stays the guaranteed fallback.
"""
import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

# Retry window if the device is briefly offline.
PUSH_TTL = 300


def _b64url_decode(value: str) -> bytes:
    """Decode a base64url string, adding back the stripped padding."""
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + pad)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _load_vapid_key():
    """Return (private_ec_key, public_b64url) or (None, None) when unset."""
    raw = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    if not raw:
        return None, None
    try:
        private = serialization.load_pem_private_key(raw.encode("utf-8"), None)
    except Exception:
        logger.warning("VAPID_PRIVATE_KEY is not a valid PEM key", exc_info=True)
        return None, None
    public = private.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return private, _b64url_encode(public)


def public_key_b64url() -> str:
    """The public key the browser needs to build a subscription."""
    return os.environ.get("VAPID_PUBLIC_KEY", "").strip()


def is_configured() -> bool:
    return bool(public_key_b64url() and _load_vapid_key()[0])


def _vapid_jwt(private_key, audience: str) -> str:
    """Sign the short-lived JWT that proves we own this push source."""
    header = _b64url_encode(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    claims = _b64url_encode(
        json.dumps(
            {
                "aud": audience,
                "exp": int(time.time()) + 12 * 3600,
                "sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@sraha.local"),
            }
        ).encode()
    )
    message = f"{header}.{claims}".encode()
    der = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
    # ES256 wants the raw r||s form, not DER.
    r, s = decode_dss_signature(der)
    signature = _b64url_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"{header}.{claims}.{signature}"


def _hkdf(length: int, info: bytes, shared: bytes, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
        backend=default_backend(),
    ).derive(shared)


def _encrypt_payload(plaintext: bytes, p256dh_b64: str, auth_b64: str) -> bytes:
    """aes128gcm content-encoding, exactly as RFC 8291 describes it."""
    server_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
    server_public = server_private.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    client_public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), _b64url_decode(p256dh_b64)
    )
    client_public_raw = client_public.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )

    shared = server_private.exchange(ec.ECDH(), client_public)
    # "auth" is the secret both sides already know; used as the HKDF salt.
    auth_secret = _b64url_decode(auth_b64)

    prk = _hkdf(32, b"WebPush: info\x00" + client_public_raw + server_public,
                shared, auth_secret)
    ikm = _hkdf(32, b"Content-Encoding: aes128gcm\x01", prk, b"")
    nonce = _hkdf(12, b"Content-Encoding: nonce\x01", prk, b"")

    salt = os.urandom(16)
    record = AESGCM(ikm).encrypt(nonce, plaintext + b"\x02", None)
    # Header: salt(16) + rs(4) + idlen(1) + our public key.
    header = salt + len(record).to_bytes(4, "big") + bytes([len(server_public)])
    return header + server_public + record


def send_push(subscription, payload: dict) -> bool:
    """Deliver `payload` to one subscription. Returns True on success.

    Never raises: a dead subscription only gets deactivated so the next
    attempt skips it.
    """
    private_key, _ = _load_vapid_key()
    if private_key is None:
        return False

    audience = "/".join(subscription.endpoint.split("/")[:3])
    try:
        body = _encrypt_payload(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            subscription.p256dh,
            subscription.auth,
        )
    except Exception:
        logger.warning("push encryption failed", exc_info=True)
        return False

    request = urllib.request.Request(subscription.endpoint, data=body, method="POST")
    request.add_header("Content-Type", "application/octet-stream")
    request.add_header("Content-Encoding", "aes128gcm")
    request.add_header("TTL", str(PUSH_TTL))
    request.add_header("Authorization", f"vapid t={_vapid_jwt(private_key, audience)}")
    request.add_header("Crypto-Key", f"p256ecdsa={public_key_b64url()}")

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            ok = 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        # 404/410 mean the subscription is gone for good — stop retrying it.
        if exc.code in (404, 410):
            subscription.is_active = False
            subscription.save(update_fields=["is_active"])
        else:
            logger.warning("push service returned %s", exc.code)
        return False
    except Exception:
        logger.warning("push request failed", exc_info=True)
        return False

    if ok:
        from django.utils import timezone

        subscription.last_used_at = timezone.now()
        subscription.save(update_fields=["last_used_at"])
    return ok


def notify_new_message(recipient) -> int:
    """Push "new message" to every active device of `recipient`.

    Returns how many devices were reached. The body is never included.
    """
    # Checked before any DB access: with no VAPID key configured there is
    # nothing to deliver to, so we never touch the database for nothing.
    if not is_configured():
        return 0

    from users.models import UserSettings

    try:
        # get_or_create: accounts without a settings row still get alerts.
        settings_row, _ = UserSettings.objects.get_or_create(user=recipient)
    except Exception:
        # A background thread can briefly fail to write while the request
        # holds the lock; never break the caller for that.
        logger.warning("push settings lookup failed", exc_info=True)
        return 0
    if not settings_row.push_notifications:
        return 0

    payload = {
        "title": "صراحة",
        "body": "لديك رسالة مجهولة جديدة 📩",
        "tag": "new-message",
        "url": "/inbox",
    }

    sent = 0
    try:
        subscriptions = list(recipient.push_subscriptions.filter(is_active=True))
    except Exception:
        return 0
    for sub in subscriptions:
        try:
            if send_push(sub, payload):
                sent += 1
        except Exception:
            logger.warning("push send failed", exc_info=True)
    return sent
