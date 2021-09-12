from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from hacktheback.forms.models import Form, Question
from hacktheback.rest.forms.openapi import id_or_type_parameter
from hacktheback.rest.forms.serializers import QuestionSerializer
from hacktheback.rest.permissions import AdminSiteModelPermissions


@extend_schema(tags=["Admin APIs", "Forms"])
@extend_schema_view(
    list=extend_schema(
        summary="List Questions in a Form",
        description="List all questions in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    retrieve=extend_schema(
        summary="Retrieve a Question in a Form",
        description="Retrieve a question in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    create=extend_schema(
        summary="Create a Question in a Form",
        description="Create a question in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    update=extend_schema(
        summary="Update a Question in a Form",
        description="Update a question in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    partial_update=extend_schema(
        summary="Partial Update a Question in a Form",
        description="Partial update a question in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
    destroy=extend_schema(
        summary="Delete a Question in a Form",
        description="Delete a question in the specified form.",
        parameters=[id_or_type_parameter("form_id_or_type")],
    ),
)
class FormQuestionsAdminViewSet(viewsets.ModelViewSet):
    queryset = Question.objects.none()
    serializer_class = QuestionSerializer
    permission_classes = (AdminSiteModelPermissions,)

    def get_queryset(self):
        """
        Filter question by form.
        """
        if not self.kwargs.get("form_id_or_type"):
            raise RuntimeError("form_id_or_type must be available in kwargs")

        id_or_type = self.kwargs.get("form_id_or_type")
        if id_or_type == "hacker_application":
            self.queryset = Question.objects.filter(
                form__type=Form.FormType.HACKER_APPLICATION
            )
        else:
            self.queryset = Question.objects.filter(form__pk=id_or_type)

        return super().get_queryset()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        id_or_type = self.kwargs.get("form_id_or_type")
        try:
            if id_or_type == "hacker_application":
                context["form"] = Form.objects.get(
                    type=Form.FormType.HACKER_APPLICATION
                )
            else:
                context["form"] = Form.objects.get(pk=id_or_type)
        except Form.DoesNotExist:
            raise Http404
        return context
