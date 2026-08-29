from django.urls import path

from users import views

app_name = "settings"

urlpatterns = [
    path("", views.UserSettingsView.as_view(), name="settings"),
    path("toggle-anonymous/", views.ToggleAnonymousView.as_view(), name="toggle-anonymous"),
    # Profile (real-name + bio)
    path("profile/", views.MyProfileView.as_view(), name="profile"),
    path("profile/avatar/", views.AvatarUploadView.as_view(), name="avatar"),
    # Premium subscription → verification badge
    path("subscribe/", views.SubscribeCreateView.as_view(), name="subscribe"),
    path("subscribe/status/", views.SubscriptionStatusView.as_view(), name="subscribe-status"),
]