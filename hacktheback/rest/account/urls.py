from django.urls import path

from hacktheback.rest.account.views import (
    JSONWebTokenBasicAuthAPIView,
    JSONWebTokenSocialAuthAPIView,
    RefreshJSONWebTokenAPIView,
    VerifyJSONWebTokenAPIView,
)

urlpatterns = [
    path("token/create/basic", JSONWebTokenBasicAuthAPIView.as_view()),
    path("token/create/social", JSONWebTokenSocialAuthAPIView.as_view()),
    path("token/refresh", RefreshJSONWebTokenAPIView.as_view()),
    path("token/verify", VerifyJSONWebTokenAPIView.as_view()),
]
