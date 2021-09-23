from django.urls import include, path
from rest_framework.routers import SimpleRouter

from hacktheback.rest.messenger.views import (
    EmailTemplateAdminViewSet,
    MessageAdminViewSet,
    RenderMJMLAdminAPIView,
    SendEmailUsingTemplateAdminAPIView,
)

router = SimpleRouter(trailing_slash=False)
router.register(
    "email-templates",
    EmailTemplateAdminViewSet,
    basename="admin-email-templates",
)
router.register("messages", MessageAdminViewSet, basename="admin-messages")

urlpatterns = [
    path(
        "render_mjml",
        RenderMJMLAdminAPIView.as_view(),
        name="admin-render_mjml",
    ),
    path("", include(router.urls)),
    path(
        "send_email_from_template",
        SendEmailUsingTemplateAdminAPIView().as_view(),
    ),
]
