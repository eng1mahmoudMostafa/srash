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
    # Uploaded media (avatars) served by Django itself.
    re_path(r"^media/(?P<path>.*)$", config_views.media_file, name="media"),
    # Real files from the Vite build (JS/CSS bundles, icons); safe fallback
    # otherwise, so hashed bundle URLs resolve over the public tunnel.
    re_path(r"^assets/(?P<path>.*)$", config_views.spa_asset, name="spa-assets"),
    re_path(r"^favicon\.ico$|^vite\.svg$", config_views.spa_asset),
    # SPA fallback: anything not /api, /admin, /static goes to the React app.
    re_path(r"^(?!api/|admin/|static/|assets/|media/).*$", config_views.spa_index, name="spa"),
]