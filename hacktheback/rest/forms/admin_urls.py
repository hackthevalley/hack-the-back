from django.urls import include, path
from rest_framework_nested import routers

from hacktheback.rest.forms.views import (
    FoodTrackingViewSet, FoodViewSet, FormQuestionOptionsAdminViewSet,
    FormQuestionsAdminViewSet, FormsAdminViewSet,
    HackerApplicationAnswerFileAdminViewSet,
    HackerApplicationResponsesAdminViewSet, WalkInAdmissionAPIView)

router = routers.SimpleRouter(trailing_slash=False)
router.register(
    "forms/hacker_application/responses/files",
    HackerApplicationAnswerFileAdminViewSet,
    basename="admin-hacker-application-form-response-files"
)
router.register(
    "forms/hacker_application/responses",
    HackerApplicationResponsesAdminViewSet,
    basename="admin-hacker-application-form-responses"
)
router.register("forms", FormsAdminViewSet, basename="admin-forms")

router.register("food", FoodViewSet, basename="food")

router.register("foodtracker", FoodTrackingViewSet, basename="all-foods")

forms_router = routers.NestedSimpleRouter(router, "forms", lookup="form")
forms_router.register(
    "questions", FormQuestionsAdminViewSet, basename="admin-form-questions"
)

form_questions_router = routers.NestedSimpleRouter(
    forms_router, "questions", lookup="question"
)
form_questions_router.register(
    "options",
    FormQuestionOptionsAdminViewSet,
    basename="admin-form-question-options"
)


urlpatterns = [
    path("", include(router.urls)),
    path("", include(forms_router.urls)),
    path("", include(form_questions_router.urls)),
    path("walkin", WalkInAdmissionAPIView.as_view())
]
