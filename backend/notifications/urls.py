from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("read-all/", views.MarkAllNotificationsReadView.as_view(), name="read-all"),
    path("<int:pk>/read/", views.MarkNotificationReadView.as_view(), name="read"),
    # Web Push (the e-mail replacement): key + device registration.
    path("push/key/", views.PushPublicKeyView.as_view(), name="push-key"),
    path(
        "push/subscribe/",
        views.PushSubscribeView.as_view(),
        name="push-subscribe",
    ),
    path(
        "push/unsubscribe/",
        views.PushUnsubscribeView.as_view(),
        name="push-unsubscribe",
    ),
]
