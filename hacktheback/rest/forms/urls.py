from rest_framework import routers

from hacktheback.rest.forms.views.answer_file import (
    HackerApplicationAnswerFileViewSet,
)
from hacktheback.rest.forms.views.form import FormsViewSet
from hacktheback.rest.forms.views.form_response import (
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
