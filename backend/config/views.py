"""Serves the built React SPA from the single backend origin.

This lets us expose the whole app (frontend + /api) through one public tunnel
without cross-origin/CSRF complications. Only the production `dist` build is
served; /api and /admin keep their normal handlers.

Performance notes:
  * Hashed bundles under /assets/ are served with immutable, long-lived caching
    so repeat visits never re-download them.
  * Pre-compressed .br / .gz siblings (produced at build time) are served with
    the matching Content-Encoding when the client supports it — this is the
    single biggest transfer-size win for the ~250KB JS bundle.
  * ETag + Last-Modified enable cheap 304 revalidation.
"""
import mimetypes
import os
import secrets
import subprocess
import threading

from django.conf import settings
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseNotFound,
    JsonResponse,
)
from django.utils.http import http_date, quote_etag


def _dist_root():
    return os.path.realpath(str(settings.FRONTEND_DIST_DIR))


def _safe_join(root, rel):
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


def _etag_for(full):
    st = os.stat(full)
    return quote_etag(f"{st.st_mtime_ns}-{st.st_size}")


def _cache_control(immutable):
    # Hashed assets: cache for a year and never revalidate.
    # index.html / icons: short cache so deploys are picked up quickly.
    return "public, max-age=31536000, immutable" if immutable else "public, max-age=3600"


def _serve_static(request, full, immutable=False):
    """Serve a file with optional pre-compression, caching and 304 support."""
    ctype, _ = mimetypes.guess_type(full)
    accept = request.META.get("HTTP_ACCEPT_ENCODING", "")
    fh = open(full, "rb")
    content_encoding = None
    # Prefer brotli (smaller), fall back to gzip.
    if "br" in accept and os.path.isfile(full + ".br"):
        fh = open(full + ".br", "rb")
        content_encoding = "br"
    elif "gzip" in accept and os.path.isfile(full + ".gz"):
        fh = open(full + ".gz", "rb")
        content_encoding = "gzip"

    etag = _etag_for(full)
    if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        fh.close()
        resp = HttpResponse(status=304)
        resp["ETag"] = etag
        resp["Cache-Control"] = _cache_control(immutable)
        return resp

    resp = FileResponse(fh, content_type=ctype)
    resp["ETag"] = etag
    resp["Last-Modified"] = http_date(os.stat(full).st_mtime)
    resp["Cache-Control"] = _cache_control(immutable)
    resp["Vary"] = "Accept-Encoding"
    if content_encoding:
        resp["Content-Encoding"] = content_encoding
    return resp


def spa_asset(request, path=None):
    """Serve a real static file that exists inside frontend/dist safely.

    Prevents directory traversal by resolving both paths and requiring the
    resolved file to live inside the dist root. Anything that is not an
    existing file falls back to the SPA index (client-side routing).
    """
    root = _dist_root()
    # Assets built by Vite live under /assets/. Any other top-level file
    # (e.g. /favicon.ico, /vite.svg) is resolved relative to the root.
    rel = os.path.join("assets", path) if path is not None else request.path.lstrip("/")
    full = _safe_join(root, rel)
    if full is not None and os.path.isfile(full):
        # Files under assets/ carry a content hash in their name -> immutable.
        immutable = rel.replace(os.sep, "/").startswith("assets/")
        return _serve_static(request, full, immutable=immutable)
    return spa_index(request)


def api_not_found(request, path=""):
    """JSON 404 for any /api/... URL that matched no real endpoint.

    Django's built-in 404 is an HTML page; the SPA fetches /api as JSON, so an
    HTML answer used to crash the client parser and surface a red error (and a
    fake "please log in" state). Every API miss must stay machine-readable.
    """
    return JsonResponse(
        {"detail": "المسار غير موجود."}, status=404
    )


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
    if full is None or not os.path.isfile(full):
        return HttpResponseNotFound()
    # Media files are stable once written; a day of caching + ETag revalidation
    # avoids re-sending the same avatar on every navigation.
    return _serve_static(request, full, immutable=False)


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
    etag = _etag_for(path)
    if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        resp = HttpResponse(status=304)
        resp["ETag"] = etag
        resp["Cache-Control"] = "no-cache"
        return resp
    fh = open(path, "rb")  # FileResponse takes ownership and closes it
    resp = FileResponse(fh, content_type="text/html")
    resp["ETag"] = etag
    resp["Last-Modified"] = http_date(os.stat(path).st_mtime)
    # Always revalidate so users pick up new asset hashes after a deploy,
    # but the ETag keeps the revalidation cheap (304, no body).
    resp["Cache-Control"] = "no-cache"
    resp["Vary"] = "Accept-Encoding"
    return resp


def deploy_webhook(request):
    """Secret-protected deploy + renew endpoint (GET).

    Why this exists
    ---------------
    PythonAnywhere's free plan cannot create scheduled tasks, and since March
    2026 a free web app stops running ~1 month after the last account activity
    ("Run until" date). So an external free cron (cron-job.org — no card
    needed) hits this URL once a day. The deploy script then runs in a
    background thread: it pulls new code from GitHub, runs migrations, and
    reloads the webapp through the official PythonAnywhere API — which both
    activates the new code and renews the "run until" date. The owner never
    has to log in again.

    Security
    --------
    The GitHub repo is PUBLIC, so the secret can never live in the code. It
    comes only from DEPLOY_WEBHOOK_SECRET (set in the server's ~/srash/.env)
    and travels as a query parameter. compare_digest keeps the comparison
    constant-time. Without the secret the endpoint answers 403.
    """
    secret = os.environ.get("DEPLOY_WEBHOOK_SECRET", "")
    provided = request.GET.get("secret", "")
    if (
        not secret
        or not provided
        or not secrets.compare_digest(provided, secret)
    ):
        return JsonResponse({"detail": "forbidden"}, status=403)

    def _run():
        log = open(os.path.expanduser("~/srash/webhook_deploy.log"), "a")
        try:
            subprocess.run(
                ["bash", os.path.expanduser("~/srash/deploy_pa.sh")],
                timeout=300,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        except Exception:
            # Any failure is already captured by the script's own logging.
            pass
        finally:
            log.close()

    threading.Thread(target=_run, daemon=True).start()
    return JsonResponse(
        {
            "status": "deploy started",
            "note": "check ~/srash/deploy.log in about a minute",
        }
    )