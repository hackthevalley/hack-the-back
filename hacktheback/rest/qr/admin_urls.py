from django.urls import path

from hacktheback.rest.qr.views import (
    QrAdmissionView,
)

# router = SimpleRouter(trailing_slash=False)
# router.register("admit", QrAdmissionView.as_view(), basename="admit")

urlpatterns = [
    path("admit", QrAdmissionView.as_view()),
]
