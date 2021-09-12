from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from hacktheback.forms.models import Form, Question, QuestionOption
from hacktheback.rest.forms.openapi import id_or_type_parameter
from hacktheback.rest.forms.serializers import QuestionOptionSerializer
from hacktheback.rest.permissions import AdminSiteModelPermissions


@extend_schema(tags=["Admin APIs", "Forms"])
@extend_schema_view(
    list=extend_schema(
        summary="List Options for a Question in a Form",
        description="List all options for the specified question in the "
        "specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    retrieve=extend_schema(
        summary="Retrieve an Option for a Question in a Form",
        description="Retrieve an option for the specified question in the "
        "specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    create=extend_schema(
        summary="Create an Option for a Question in a Form",
        description="Create an option for the specified question in the "
        "specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    update=extend_schema(
        summary="Update an Option for a Question in a Form",
        description="Update an option for the specified question in the "
        "specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    partial_update=extend_schema(
        summary="Partial Update an Option for a Question in a Form",
        description="Partial update an option for the specified question "
        "in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    destroy=extend_schema(
        summary="Delete an Option for a Question in a Form",
        description="Delete an option for the specified question in the "
        "specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
)
class FormQuestionOptionsAdminViewSet(viewsets.ModelViewSet):
    queryset = QuestionOption.objects.none()
    serializer_class = QuestionOptionSerializer
    permission_classes = (AdminSiteModelPermissions,)

    def get_queryset(self):
        """
        Filter option by question and form.
        """
        if not self.kwargs.get("form_id_or_type") or not self.kwargs.get(
            "question_pk"
        ):
            raise RuntimeError(
                "form_id_or_type or question_id must be available in kwargs"
            )

        form_id_or_type = self.kwargs.get("form_id_or_type")
        question_id = self.kwargs.get("question_pk")
        if form_id_or_type == "hacker_application":
            self.queryset = QuestionOption.objects.filter(
                question__pk=question_id,
                question__form__type=Form.FormType.HACKER_APPLICATION,
            )
        else:
            self.queryset = QuestionOption.objects.filter(
                question__pk=question_id, question__form__pk=form_id_or_type
            )

        return super().get_queryset()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        form_id_or_type = self.kwargs.get("form_id_or_type")
        question_id = self.kwargs.get("question_pk")

        try:
            if form_id_or_type == "hacker_application":
                context["form"] = Form.objects.get(
                    type=Form.FormType.HACKER_APPLICATION
                )
            else:
                context["form"] = Form.objects.get(pk=form_id_or_type)
        except Form.DoesNotExist:
            raise Http404
        try:
            context["question"] = Question.objects.get(pk=question_id)
        except Question.DoesNotExist:
            raise Http404
        return context
