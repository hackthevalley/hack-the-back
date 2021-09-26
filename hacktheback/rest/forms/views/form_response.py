from typing import List

from django.db import transaction
from django.http import Http404
from django.utils.translation import ugettext as _
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from hacktheback.forms import utils
from hacktheback.forms.models import (
    Form,
    FormResponse,
    HackathonApplicant,
    Question,
)
from hacktheback.rest.exceptions import ConflictError
from hacktheback.rest.forms.common import answer_question_in_form_response
from hacktheback.rest.forms.filters import (
    HackerApplicationResponsesAdminFilter,
)
from hacktheback.rest.forms.serializers import (
    AnswerSerializer,
    HackerApplicationBatchStatusUpdateSerializer,
    HackerApplicationResponseAdminSerializer,
    HackerApplicationResponseSerializer,
    HackerApplicationSummarySerializer,
)
from hacktheback.rest.pagination import StandardResultsPagination
from hacktheback.rest.permissions import AdminSiteModelPermissions, IsOwner


@extend_schema(tags=["Hacker APIs", "Forms"])
class HackerApplicationResponsesViewSet(viewsets.GenericViewSet):
    queryset = FormResponse.objects.filter(
        form__type=Form.FormType.HACKER_APPLICATION,
        form__is_draft=False,
    )
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    serializer_class = HackerApplicationResponseSerializer

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
            raise PermissionDenied(
                detail=_(
                    "The hacker application has "
                    "already been submitted. It "
                    "cannot be edited anymore."
                )
            )
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
        responses={200: AnswerSerializer},
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
        data = answer_question_in_form_response(
            form_response=form_response, answer_data=request.data
        )
        return Response(data)

    @extend_schema(
        summary="Submit the Current User's Hacker Application",
        request=None,
        responses={
            204: OpenApiResponse(
                description="The current user's hacker application has been "
                "submitted."
            )
        },
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
            instance.form.questions.filter(required=True)
        )
        answered = list(instance.answers.all())
        answered_questions = list(
            Question.objects.filter(answers__in=answered)
        )
        missing_questions: List[Question] = utils.get_missing_questions(
            required_questions, answered_questions
        )
        if len(missing_questions) > 0:
            raise ConflictError(
                detail=_(
                    "Not all required questions have been answered: {"
                    "questions}"
                ).format(
                    **{
                        "questions": "; ".join(
                            str(q) for q in missing_questions
                        )
                    }
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

    def _set_applicant_status(self, requirement, new_status) -> Response:
        instance = self.get_object()
        if instance.applicant.status != requirement:
            raise Http404
        instance.applicant.status = new_status
        instance.applicant.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Accept Invitation to Join Hackathon",
        request=None,
        responses={
            204: OpenApiResponse(
                description="The current user has accepted their invitation "
                "to join the hackathon."
            )
        },
    )
    @action(methods=["POST"], detail=False)
    def accept_invite(self, request, *args, **kwargs):
        """
        Accept invitation to join hackathon. Returns 404 if condition not met.
        """
        return self._set_applicant_status(
            HackathonApplicant.Status.ACCEPTED,
            HackathonApplicant.Status.ACCEPTED_INVITE,
        )

    @extend_schema(
        summary="Reject Invitation to Join Hackathon",
        request=None,
        responses={
            204: OpenApiResponse(
                description="The current user has rejected their invitation "
                "to join the hackathon."
            )
        },
    )
    @action(methods=["POST"], detail=False)
    def reject_invite(self, request, *args, **kwargs):
        """
        Reject invitation to join hackathon. Returns 404 if condition not met.
        """
        return self._set_applicant_status(
            HackathonApplicant.Status.ACCEPTED,
            HackathonApplicant.Status.REJECTED_INVITE,
        )


@extend_schema(tags=["Admin APIs", "Forms"])
@extend_schema_view(
    list=extend_schema(
        summary="List Hacker Applications",
        description="List hacker applications.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a Hacker Application",
        description="Retrieve a hacker application.",
    ),
    update=extend_schema(
        summary="Update a Hacker Application",
        description="Update a hacker application.",
    ),
    partial_update=extend_schema(
        summary="Partial update a Hacker Application",
        description="Partial update a hacker application.",
    ),
    answer_question=extend_schema(
        summary="Answer a Question in a Hacker Application",
        request=AnswerSerializer,
        responses={200: AnswerSerializer},
    ),
    batch_status_update=extend_schema(
        summary="Change the Status of Hacker Application(s)",
        request=HackerApplicationBatchStatusUpdateSerializer,
        responses={
            "204": OpenApiResponse(
                description="The hacker applications have had their statuses "
                "changed."
            )
        },
    ),
    overview=extend_schema(
        summary="Overview of Hacker Applications",
        request=None,
        responses={"200": HackerApplicationSummarySerializer},
    ),
)
class HackerApplicationResponsesAdminViewSet(
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = FormResponse.objects.filter(
        form__type=Form.FormType.HACKER_APPLICATION
    )
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = HackerApplicationResponseAdminSerializer
    pagination_class = StandardResultsPagination
    filterset_class = HackerApplicationResponsesAdminFilter

    @action(methods=["PUT"], detail=True)
    def answer_question(self, request, *args, **kwargs):
        """
        Answer a question in the specified hacker application. This is
        idempotent in that one answer will be created if it doesn't exist and
        will be updated if it does exist.
        """
        data = answer_question_in_form_response(
            form_response=self.get_object(), answer_data=request.data
        )
        return Response(data)

    @action(detail=False, methods=["POST"])
    def batch_status_update(self, request, *args, **kwargs):
        """
        Update the state of one or more hacker applications.
        """
        # Validate data
        serializer = HackerApplicationBatchStatusUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        # Gather data
        new_status = serializer.data.get("status")
        responses = serializer.data.get("responses")
        with transaction.atomic():
            # Retrieve all associated HackathonApplicant objects
            ha_objs = HackathonApplicant.objects.filter(
                application__id__in=responses
            )
            for ha_obj in ha_objs:
                ha_obj.status = new_status
            # Update status of those objects
            HackathonApplicant.objects.bulk_update(ha_objs, ["status"])

            # Also, set the form response `is_draft` to `True` if status
            # changes to `APPLYING`. Otherwise, all status changes will have
            # form response `is_draft` to `False`
            response_objs = FormResponse.objects.filter(id__in=responses)
            if new_status == HackathonApplicant.Status.APPLYING:
                for response_obj in response_objs:
                    response_obj.is_draft = True
            else:
                for response_obj in response_objs:
                    response_obj.is_draft = False
            FormResponse.objects.bulk_update(response_objs, ["is_draft"])

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["GET"], detail=False)
    def overview(self, request, *args, **kwargs):
        """
        General overview of hacker applications.
        """
        response = {"overview": []}
        for status, _ in HackathonApplicant.Status.choices:
            response["overview"].append(
                {
                    "status": status,
                    "count": HackathonApplicant.objects.filter(
                        status=status
                    ).count(),
                },
            )
        serializer = HackerApplicationSummarySerializer(data=response)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
