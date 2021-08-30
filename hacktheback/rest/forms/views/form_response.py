from typing import List

from django.db import transaction
from django.http import Http404
from django.utils.translation import ugettext as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from hacktheback.forms import utils
from hacktheback.forms.models import (
    Answer,
    Form,
    FormResponse,
    HackathonApplicant,
    Question,
)
from hacktheback.rest.exceptions import ConflictError
from hacktheback.rest.forms.serializers import (
    AnswerSerializer,
    FormResponseSerializer,
)
from hacktheback.rest.permissions import IsOwner


@extend_schema(tags=["Hacker APIs", "Forms"])
class HackerApplicationResponsesViewSet(viewsets.GenericViewSet):
    queryset = FormResponse.objects.filter(
        form__type=Form.FormType.HACKER_APPLICATION,
        form__is_draft=False,
    )
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    serializer_class = FormResponseSerializer

    def get_queryset(self):
        """
        Query by the current user as well.
        """
        self.queryset = self.queryset.filter(user=self.request.user)
        return super().get_queryset()

    def get_object(self):
        """
        Get the current user's hacker application.
        """
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset)
        self.check_object_permissions(self.request, obj)
        return obj

    @staticmethod
    def _do_form_open_check() -> None:
        try:
            get_object_or_404(Form.objects.open_hacker_application())
        except Http404:
            raise NotFound(
                detail=_(
                    "The hacker application form is either closed or does "
                    "not exist."
                )
            )

    def _do_response_does_not_exist_check(self) -> None:
        try:
            response: FormResponse = self.get_object()
            if response:
                raise ConflictError(
                    detail=_(
                        "A hacker application already exists for the user."
                    )
                )
        except Http404:
            pass

    def _do_response_not_in_draft_check(self) -> FormResponse:
        response: FormResponse = self.get_object()
        if not response.is_draft:
            raise PermissionDenied(detail=_("The hacker application has "
                                            "already been submitted. It "
                                            "cannot be edited anymore."))
        return response

    @extend_schema(
        summary="Retrieve the Current User's Hacker Application",
        responses={
            201: OpenApiResponse(
                description="The current user's hacker application."
            )
        },
    )
    def list(self, request, *args, **kwargs):
        """
        Retrieve the current user's hacker application.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(summary="Create the Current User's Hacker Application")
    def create(self, request, *args, **kwargs):
        """
        Create a hacker application for the current user. If the application is
        in draft, do not place an unanswered answer in the `answers` field.
        Once the application is submitted (i.e. not in draft), then the
        `answers` field must at least contain all the required answers.
        """
        # Cannot create a hacker application if the form is not open.
        self._do_form_open_check()
        # Cannot create a new response if one already exists for the user
        self._do_response_does_not_exist_check()
        # Create the hacker application
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Answer a Question in the Current User's Hacker Application",
        request=AnswerSerializer,
        responses={200: AnswerSerializer}
    )
    @action(methods=["PUT"], detail=False)
    def answer_question(self, request, *args, **kwargs):
        """
        Answer a question in the current user's hacker application. This is
        idempotent in that one answer will be created if it doesn't exist and
        will be updated if it does exist.
        """
        # Cannot update a hacker application if the form is not open.
        self._do_form_open_check()
        # Cannot update a response that has already been submitted.
        form_response: FormResponse = self._do_response_not_in_draft_check()
        # Validate request data
        serializer = AnswerSerializer(
            data=request.data,
            context={"form_response": form_response}
        )
        serializer.is_valid(raise_exception=True)
        try:
            # Get answer to question if it exists
            question: Question = serializer.validated_data.get("question")
            answer = Answer.objects.get(
                question=question,
                response=form_response
            )
            serializer.instance = answer
        except Answer.DoesNotExist:
            pass
        # Create or update the answer
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        summary="Submit the Current User's Hacker Application",
        request=None,
        responses={
            204: OpenApiResponse(
                description="The current user's hacker application has been "
                            "submitted."
            )
        }
    )
    @action(methods=["POST"], detail=False)
    def submit(self, request, *args, **kwargs):
        """
        Submits the current user's hacker application. In essence, it sets
        the `is_draft` flag to `False`. A user can no longer edit the
        application after this.
        """
        # Cannot update a hacker application if the form is not open.
        self._do_form_open_check()
        # Cannot submit a response that has already been submitted.
        instance: FormResponse = self._do_response_not_in_draft_check()
        # Check if all required questions have been answered.
        required_questions = list(
            instance.form.questions.filter(required=True))
        answered = list(instance.answers.all())
        answered_questions = list(
            Question.objects.filter(answers__in=answered)
        )
        missing_questions: List[Question] = utils.get_missing_questions(
            required_questions,
            answered_questions
        )
        if len(missing_questions) > 0:
            raise ConflictError(
                detail=_(
                    "Not all required questions have been answered: {"
                    "questions}").format(
                        **{"questions": "; ".join(
                            str(q) for q in missing_questions
                        )}
                )
            )
        with transaction.atomic():
            # Submit current user's hacker application
            instance.is_draft = False
            instance.save()
            # Set the status of the HackerApplicant object to APPLIED
            instance.applicant.status = HackathonApplicant.Status.APPLIED
            instance.applicant.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
