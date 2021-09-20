from django.urls import path

from hacktheback.rest.account.views import (
    CurrentUserAPIView,
    CurrentUserPermissionsAPIView,
    CurrentUserSetPasswordAPIView,
    JSONWebTokenBasicAuthAPIView,
    JSONWebTokenSocialAuthAPIView,
    RefreshJSONWebTokenAPIView,
    RegisterUserAPIView,
    UserActivationAPIView,
    UserResendActivationAPIView,
    UserResetPasswordAPIView,
    UserResetPasswordConfirmAPIView,
    VerifyJSONWebTokenAPIView,
)

urlpatterns = [
    path("auth/token/create/basic", JSONWebTokenBasicAuthAPIView.as_view()),
    path("auth/token/create/social", JSONWebTokenSocialAuthAPIView.as_view()),
    path("auth/token/refresh", RefreshJSONWebTokenAPIView.as_view()),
    path("auth/token/verify", VerifyJSONWebTokenAPIView.as_view()),
    path("users", RegisterUserAPIView.as_view()),
    path("users/activation", UserActivationAPIView.as_view()),
    path("users/resend_activation", UserResendActivationAPIView.as_view()),
    path("users/reset_password", UserResetPasswordAPIView.as_view()),
    path(
        "users/reset_password_confirm",
        UserResetPasswordConfirmAPIView.as_view(),
    ),
    path("users/me", CurrentUserAPIView.as_view()),
    path("users/me/set_password", CurrentUserSetPasswordAPIView.as_view()),
    path("users/me/permissions", CurrentUserPermissionsAPIView.as_view()),
]
