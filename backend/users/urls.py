from django.urls import path

from users import views

app_name = "auth"

urlpatterns = [
    path("csrf/", views.CsrfTokenView.as_view(), name="csrf"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("verify-email/send/", views.SendVerificationEmailView.as_view(), name="verify-send"),
    path("verify-email/", views.VerifyEmailTokenView.as_view(), name="verify"),
]