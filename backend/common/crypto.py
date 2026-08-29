"""Field-level encryption helpers (AES-256-GCM).

The encryption key is loaded from `settings.MESSAGE_ENCRYPTION_KEY` (Base64 of a
32-byte key) and is never stored inside the database or committed to Git.
"""
import base64
import hashlib
import hmac
import os

from django.conf import settings

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def sign_ip(ip: str) -> str:
    """One-way HMAC of a client IP. The raw IP is never persisted."""
    key = settings.IP_HMAC_KEY.encode("utf-8")
    return hmac.new(key, ip.encode("utf-8"), hashlib.sha256).hexdigest()


def _load_key() -> bytes:
    raw = settings.MESSAGE_ENCRYPTION_KEY
    if isinstance(raw, str):
        raw = raw.encode("ascii")
    try:
        return base64.b64decode(raw)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError(
            "MESSAGE_ENCRYPTION_KEY must be a base64-encoded AES-256 key."
        ) from exc


def encrypt_message(plaintext: str) -> tuple[str, str]:
    """Return (base64 ciphertext, base64 nonce)."""
    key = _load_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce).decode("ascii"),
    )


def decrypt_message(ciphertext_b64: str, nonce_b64: str) -> str:
    key = _load_key()
    aesgcm = AESGCM(key)
    ciphertext = base64.b64decode(ciphertext_b64)
    nonce = base64.b64decode(nonce_b64)
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def encrypt_bytes(data: bytes) -> tuple[bytes, bytes]:
    """Encrypt raw bytes (e.g. message images). Return (ciphertext, nonce)."""
    key = _load_key()
    nonce = os.urandom(12)
    return AESGCM(key).encrypt(nonce, data, None), nonce


def decrypt_bytes(ciphertext: bytes, nonce: bytes) -> bytes:
    """Decrypt raw bytes produced by `encrypt_bytes`."""
    key = _load_key()
    return AESGCM(key).decrypt(nonce, ciphertext, None)