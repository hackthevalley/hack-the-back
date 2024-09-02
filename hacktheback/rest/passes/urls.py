from django.urls import path

from hacktheback.rest.passes.views import (
    DownloadApplePass,
)

urlpatterns = [
    path("apple", DownloadApplePass.as_view()),
]
