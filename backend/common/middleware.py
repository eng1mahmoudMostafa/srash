"""Request middleware: lightweight "last seen" tracking.

Updates User.last_seen_at for authenticated users at most once per minute
(cache-throttled) to keep DB writes negligible.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone


class LastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            key = f"lastseen:{user.pk}"
            if not cache.get(key):
                cache.set(key, 1, 60)
                # request.user is a SimpleLazyObject; type(user) would be
                # SimpleLazyObject (no .objects). Use the real user model.
                get_user_model().objects.filter(pk=user.pk).update(
                    last_seen_at=timezone.now()
                )
        return response