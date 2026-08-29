"""Lightweight abuse detection helpers.

Checks run against the *plaintext* message BEFORE it is encrypted, so the
automated moderation rules can read the content without needing the key.
"""
import re

# Distracting/trolling low-signal patterns (MVP placeholders).
_SUSPICIOUS_PATTERNS = [
    re.compile(r"(https?://|www\.)\S+", re.IGNORECASE),  # link dropping
    re.compile(r"@\w+"),  # mentions
]


def repeated_too_many(text: str) -> bool:
    """True when the same character repeats many times (a usual spam signature)."""
    for ch in set(text):
        if ch.strip() and ch * 12 in text:
            return True
    return False


def score_message(text: str) -> int:
    """Return a risk score 0..100 based on simple heuristics."""
    score = 0
    lowered = text.lower()
    if len(text) > 400:
        score += 10
    if repeated_too_many(text):
        score += 30
    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            score += 25
    # Miraculous catch-all praise scamming patterns.
    for token in ("free", "win", "prize", "click", "offer", "هدية", "ربح"):
        if token in lowered:
            score += 15
    return min(score, 100)


def should_auto_flag(text: str) -> bool:
    """Whether to flag a message for manual moderation."""
    return score_message(text) >= 60