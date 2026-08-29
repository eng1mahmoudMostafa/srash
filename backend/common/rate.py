"""Lightweight rate limiting built on Django's cache (Redis in production).

Keys are derived from a one-way HMAC of the client IP, so the raw IP is never
stored alongside messages (see `common.crypto.sign_ip`).
"""
import time

from django.conf import settings
from django.core.cache import cache

from common.crypto import sign_ip


class RateLimitExceeded(Exception):
    """Raised when a source exceeds an allowed window."""

    def __init__(self, message="Too many requests. Please try again later."):
        super().__init__(message)
        self.message = message


def client_ip(request) -> str:
    """Best-effort client IP. In production Nginx sets X-Forwarded-For and the
    server should be configured to trust only its own proxy headers."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _window_key(signature: str, period: int) -> str:
    bucket = int(time.time()) // period
    return f"rl:{signature}:{period}:{bucket}"


class WindowLimiter:
    """Fixed-window counter stored in cache."""

    def __init__(self, prefix: str, limit: int, window_seconds: int):
        self.prefix = prefix
        self.limit = limit
        self.window = window_seconds

    def check(self, signature: str, cost: int = 1):
        key = f"{self.prefix}:{_window_key(signature, self.window)}"
        try:
            current = cache.incr(key, cost)
        except ValueError:
            cache.set(key, cost, self.window)
            current = cost
        if current > self.limit:
            raise RateLimitExceeded()
        return current


class RichLimiter(WindowLimiter):
    """Two-window limiter that raises when *either* window is exceeded."""

    def __init__(self, prefix: str, per_minute: int, per_hour: int):
        self.per_minute = per_minute
        self.per_hour = per_hour
        super().__init__(prefix, per_minute, 60)

    def check(self, signature: str, cost: int = 1):
        # RateLimitExceeded for minute window.
        super().check(signature, cost)
        hourly = WindowLimiter(f"{self.prefix}:hour", self.per_hour, 3600)
        hourly.check(signature, cost)


def check_message_rate_limit(request) -> None:
    """Enforce per-source limits on message creation."""
    signature = sign_ip(client_ip(request))
    limiter = RichLimiter(
        "msg",
        settings.RATE_LIMIT_PER_MINUTE,
        settings.RATE_LIMIT_PER_HOUR,
    )
    limiter.check(signature)


def check_login_rate_limit(request) -> None:
    """Brute-force protection on the login endpoint (per-IP fixed window)."""
    signature = sign_ip(client_ip(request))
    limiter = WindowLimiter("login", 10, 300)  # 10 attempts / 5 minutes
    limiter.check(signature)