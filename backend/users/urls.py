from django.urls import path

from users import views

app_name = "auth"

urlpatterns = [
    path("csrf/", views.CsrfTokenView.as_view(), name="csrf"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path(
        "change-password/",
        views.ChangePasswordView.as_view(),
        name="change-password",
    ),
    # Password recovery WITHOUT e-mail: the account's own question.
    path(
        "recovery/",
        views.PasswordRecoveryStartView.as_view(),
        name="recovery",
    ),
    path(
        "recovery-confirm/",
        views.PasswordRecoveryConfirmView.as_view(),
        name="recovery-confirm",
    ),
]