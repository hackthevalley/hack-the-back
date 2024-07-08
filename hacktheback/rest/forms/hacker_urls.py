from rest_framework import routers
from django.urls import path
from hacktheback.rest.forms.views import (
    FormsViewSet,
    HackerApplicationAnswerFileViewSet,
    HackerApplicationResponsesViewSet,
)

router = routers.SimpleRouter(trailing_slash=False)
router.register("forms", FormsViewSet)
router.register(
    "forms/hacker_application/response", HackerApplicationResponsesViewSet
)
router.register(
    "forms/hacker_application/response/files",
    HackerApplicationAnswerFileViewSet,
)

urlpatterns = router.urls
