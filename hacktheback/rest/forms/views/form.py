from django.utils import timezone
from django.utils.translation import ugettext as _
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from hacktheback.forms.models import Form
from hacktheback.rest.exceptions import ConflictError
from hacktheback.rest.forms.openapi import id_or_type_parameter
from hacktheback.rest.forms.serializers import FormSerializer
from hacktheback.rest.pagination import StandardResultsPagination
from hacktheback.rest.permissions import AdminSiteModelPermissions


class IdOrTypeLookupMixin:
    lookup_field = None
    lookup_url_kwarg = "id_or_type"

    def get_object(self):
        """
        Returns the object the view is displaying.
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg

        assert self.lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf.'
            % (self.__class__.__name__, lookup_url_kwarg)
        )

        lookup_value = self.kwargs[lookup_url_kwarg]
        if lookup_value == "hacker_application":
            filter_kwargs = {"type": Form.FormType.HACKER_APPLICATION}
        else:
            filter_kwargs = {"pk": lookup_value}
        obj = get_object_or_404(queryset, **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        return obj


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


@extend_schema(tags=["Admin APIs", "Forms"])
@extend_schema_view(
    list=extend_schema(summary="List Forms", description="List all forms."),
    retrieve=extend_schema(
        summary="Retrieve a Form",
        description="Retrieve a form.",
        parameters=[id_or_type_parameter()],
    ),
    create=extend_schema(
        summary="Create a Form", description="Create a form."
    ),
    update=extend_schema(
        summary="Update a Form",
        description="Update a form.",
        parameters=[id_or_type_parameter()],
    ),
    partial_update=extend_schema(
        summary="Partial Update a Form",
        description="Partial update a form.",
        parameters=[id_or_type_parameter()],
    ),
    destroy=extend_schema(
        summary="Delete a Form",
        description="Delete a form.",
        parameters=[id_or_type_parameter()],
    ),
    publish=extend_schema(
        summary="Publish a Form",
        description="Publish a form. This sets `is_draft` to `False`.",
        parameters=[id_or_type_parameter()],
        request=None,
        responses={
            "204": OpenApiResponse(description="Form published successfully."),
        },
    ),
    unpublish=extend_schema(
        summary="Unpublish a Form",
        description="Unpublish a form. This sets `is_draft` to `True`.",
        parameters=[id_or_type_parameter()],
        request=None,
        responses={
            "204": OpenApiResponse(
                description="Form unpublished successfully."
            ),
        },
    ),
)
class FormsAdminViewSet(IdOrTypeLookupMixin, viewsets.ModelViewSet):
    queryset = Form.objects.all()
    serializer_class = FormSerializer
    pagination_class = StandardResultsPagination
    permission_classes = (AdminSiteModelPermissions,)

    def perform_create(self, serializer):
        # If the form we are creating is of type hacker application, raise
        # conflict error if one that already exists.
        type_to_create = serializer.data.get("type", None)
        if type_to_create == Form.FormType.HACKER_APPLICATION:
            raise ConflictError(
                detail=_("A hacker application form already exists.")
            )
        serializer.save()

    @action(detail=True, methods=["POST"])
    def publish(self, request, id_or_type=None):
        form = self.get_object()
        form.is_draft = False
        form.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["POST"])
    def unpublish(self, request, id_or_type=None):
        form = self.get_object()
        form.is_draft = True
        form.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
