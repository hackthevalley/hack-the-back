from django.urls import path

from hacktheback.rest.account.views import (
    JSONWebTokenBasicAuthAPIView,
    JSONWebTokenSocialAuthAPIView,
    RefreshJSONWebTokenAPIView,
    VerifyJSONWebTokenAPIView,
)

urlpatterns = [
    path("auth/token/create/basic", JSONWebTokenBasicAuthAPIView.as_view()),
    path("auth/token/create/social", JSONWebTokenSocialAuthAPIView.as_view()),
    path("auth/token/refresh", RefreshJSONWebTokenAPIView.as_view()),
    path("auth/token/verify", VerifyJSONWebTokenAPIView.as_view()),
]
