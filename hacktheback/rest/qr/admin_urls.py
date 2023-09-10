from django.urls import path

from hacktheback.rest.qr.views import (
    QrAdmissionView,
)

urlpatterns = [
    path("scan", QrAdmissionView.as_view()),
]
