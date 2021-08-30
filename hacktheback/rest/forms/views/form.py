from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404

from hacktheback.forms.models import Form
from hacktheback.rest.forms.serializers import FormSerializer


@extend_schema(tags=["Hacker APIs", "Forms"])
class FormsViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Form.objects.filter(
        is_draft=False,
        start_at__lte=timezone.now(),
        end_at__gte=timezone.now(),
    )
    authentication_classes = ()
    serializer_class = FormSerializer

    @extend_schema(summary="List Forms")
    def list(self, request, *args, **kwargs):
        """
        List all forms that have been published between their `start_at` and
        `end_at` times.
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Retrieve a Form")
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a form that has been published between its `start_at` and
        `end_at` times.
        """
        return super().retrieve(request, *args, **kwargs)

    def get_hacker_application_form(self):
        queryset = self.filter_queryset(self.get_queryset())
        return get_object_or_404(
            queryset, type=Form.FormType.HACKER_APPLICATION
        )

    @extend_schema(summary="Retrieve the Hacker Application Form")
    @action(detail=False)
    def hacker_application(self, request, *args, **kwargs):
        """
        Retrieve the hacker application form that has been published between
        its `start_at` and `end_at` times.
        """
        self.get_object = self.get_hacker_application_form
        return self.retrieve(request, *args, **kwargs)
