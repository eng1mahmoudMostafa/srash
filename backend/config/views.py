"""Serves the built React SPA from the single backend origin.

This lets us expose the whole app (frontend + /api) through one public tunnel
without cross-origin/CSRF complications. Only the production `dist` build is
served; /api and /admin keep their normal handlers.
"""
import os

from django.conf import settings
from django.http import FileResponse, HttpResponseNotFound


def _dist_root():
    return os.path.realpath(str(settings.FRONTEND_DIST_DIR))


def _safe_join(root: str, rel: str) -> str | None:
    """Resolve `rel` under `root`, returning None on any traversal attempt."""
    try:
        full = os.path.realpath(os.path.join(root, rel))
    except (ValueError, OSError):
        return None
    # startswith(root + sep) blocks both "../" escapes and sibling dirs
    # that merely share a prefix (e.g. /dist2).
    if full.startswith(root + os.sep) or full == root:
        return full
    return None


def spa_asset(request, path=None):
    """Serve a real static file that exists inside frontend/dist safely.

    Prevents directory traversal by resolving both paths and requiring the
    resolved file to live inside the dist root. Anything that is not an
    existing file falls back to the SPA index (client-side routing).
    """
    root = _dist_root()
    # Assets built by Vite live under /assets/. Any other top-level file
    # (e.g. /favicon.ico, /vite.svg) is resolved relative to the root.
    rel = os.path.join("assets", path) if path is not None else (
        request.path.lstrip("/")
    )
    full = _safe_join(root, rel)
    if full is not None and os.path.isfile(full):
        return FileResponse(open(full, "rb"))  # content-type guessed by ext
    return spa_index(request)


def media_file(request, path):
    """Serve uploaded media (avatars) safely — no traversal outside MEDIA_ROOT.

    Message attachments (message_images/) are intentionally NOT served here:
    they are recipient-only and must go through the authenticated
    /api/messages/<id>/image/ endpoint, never a public media URL.
    """
    norm = path.replace("\\", "/").lstrip("/")
    if norm.startswith("message_images/") or "/message_images/" in f"/{norm}":
        return HttpResponseNotFound()
    root = os.path.realpath(str(getattr(settings, "MEDIA_ROOT", "")))
    if not root or not os.path.isdir(root):
        return HttpResponseNotFound()
    full = _safe_join(root, path)
    if full is None:
        return HttpResponseNotFound()
    if os.path.isfile(full):
        return FileResponse(open(full, "rb"))  # type guessed from extension
    return HttpResponseNotFound()


def spa_index(request, *args, **kwargs):
    """Return the SPA index.html for any unmatched (non-API) path.

    Routing is entirely client-side; /api and /admin are matched before this
    fallback by the URL config.
    """
    path = os.path.join(settings.FRONTEND_DIST_DIR, "index.html")
    if not os.path.exists(path):
        return HttpResponseNotFound(
            "Frontend build not found. Run: cd frontend && npm run build"
        )
    fh = open(path, "rb")  # FileResponse takes ownership and closes it
    return FileResponse(fh, content_type="text/html")