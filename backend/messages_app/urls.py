from django.urls import path

from messages_app import views
from moderation import views as moderation_views

app_name = "messages"

urlpatterns = [
    path("", views.MessageSendView.as_view(), name="send"),
    path("inbox/", views.MessageListView.as_view(), name="inbox"),
    path("sent/", views.SentMessagesView.as_view(), name="sent"),
    path(
        "<int:pk>/delete-for-recipient/",
        views.SentMessageDeleteForRecipientView.as_view(),
        name="delete-for-recipient",
    ),
    path("<int:pk>/", views.MessageDetailView.as_view(), name="detail"),
    path("<int:pk>/reply/", views.MessageReplyView.as_view(), name="reply"),
    path("<int:pk>/image/", views.MessageImageView.as_view(), name="image"),
    path(
        "<int:message_id>/report/",
        moderation_views.CreateReportView.as_view(),
        name="report",
    ),
]