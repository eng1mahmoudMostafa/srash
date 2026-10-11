from django.contrib import admin
from django.urls import include, path, re_path

from config import views as config_views
from users import views as users_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/stats/", users_views.GlobalStatsView.as_view(), name="global-stats"),
    path("api/auth/", include("users.urls")),
    path("api/users/", include("users.profile_urls")),
    path("api/messages/", include("messages_app.urls")),
    path("api/settings/", include("users.settings_urls")),
    path("api/notifications/", include("notifications.urls")),
    # Uploaded media (avatars) served by Django itself.
    re_path(r"^media/(?P<path>.*)$", config_views.media_file, name="media"),
    # Real files from the Vite build (JS/CSS bundles, icons); safe fallback
    # otherwise, so hashed bundle URLs resolve over the public tunnel.
    re_path(r"^assets/(?P<path>.*)$", config_views.spa_asset, name="spa-assets"),
    # The service worker must reach the browser as real JavaScript served
    # from the site root — it has to exist before the SPA fallback below,
    # otherwise /sw.js falls through to index.html and registration dies
    # with "The script has an unsupported MIME type ('text/html')".
    re_path(r"^sw\.js$", config_views.spa_asset, name="service-worker"),
    # Notification chime (played by the bell / push handler).
    re_path(r"^notify\.wav$", config_views.spa_asset, name="notify-sound"),
    # PWA manifest + icons (phone notifications show the app icon; without
    # these the install prompt / notification icon silently breaks).
    re_path(
        r"^manifest\.webmanifest$|^icon-192\.png$|^icon-512\.png$|^icon\.svg$|^favicon\.ico$",
        config_views.spa_asset,
    ),
    # Any /api/... path that matched no endpoint above must answer JSON —
    # Django's HTML 404 page used to break the SPA's JSON parsing.
    re_path(r"^api/", config_views.api_not_found, name="api-not-found"),
    # SPA fallback: anything not /api, /admin, /static goes to the React app.
    re_path(r"^(?!api/|admin/|static/|assets/|media/).*$", config_views.spa_index, name="spa"),
]