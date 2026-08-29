from django.urls import path

from users import views

app_name = "users"

urlpatterns = [
    path("<str:username>/", views.PublicProfileView.as_view(), name="public-profile"),
]