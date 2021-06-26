from django.urls import path

from hacktheback.rest.account.views.auth_token import (
    JSONWebTokenBasicAuthAPIView,
    JSONWebTokenSocialAuthAPIView,
    RefreshJSONWebTokenAPIView,
    VerifyJSONWebTokenAPIView,
)
from hacktheback.rest.account.views.current_user import (
    CurrentUserAPIView,
    CurrentUserSetPasswordAPIView,
)
from hacktheback.rest.account.views.user import (
    UserActivationAPIView,
    UserAPIView,
    UserResendActivationAPIView,
    UserResetPasswordAPIView,
    UserResetPasswordConfirmAPIView,
)

urlpatterns = [
    path("auth/token/create/basic", JSONWebTokenBasicAuthAPIView.as_view()),
    path("auth/token/create/social", JSONWebTokenSocialAuthAPIView.as_view()),
    path("auth/token/refresh", RefreshJSONWebTokenAPIView.as_view()),
    path("auth/token/verify", VerifyJSONWebTokenAPIView.as_view()),
    path("users", UserAPIView.as_view()),
    path("users/activation", UserActivationAPIView.as_view()),
    path("users/resend_activation", UserResendActivationAPIView.as_view()),
    path("users/reset_password", UserResetPasswordAPIView.as_view()),
    path(
        "users/reset_password_confirm",
        UserResetPasswordConfirmAPIView.as_view(),
    ),
    path("users/me", CurrentUserAPIView.as_view()),
    path("users/me/set_password", CurrentUserSetPasswordAPIView.as_view()),
]
