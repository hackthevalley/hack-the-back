from django.contrib.auth.models import Group
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet

from hacktheback.rest.account.serializers import GroupSerializer
from hacktheback.rest.permissions import AdminSiteModelPermissions


@extend_schema(tags=["Admin APIs", "Account"])
@extend_schema_view(
    list=extend_schema(
        summary="List Groups",
        description="List groups that an admin user can be in.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a Group",
        description="Retrieve a group that an admin user can be in.",
    ),
    create=extend_schema(
        summary="Create a Group",
        description="Create a group that an admin user can be in.",
    ),
    update=extend_schema(
        summary="Update a Group",
        description="Update a group that an admin user can be in.",
    ),
    partial_update=extend_schema(
        summary="Partial Update a Group",
        description="Partial update a group that an admin user can be in.",
    ),
    destroy=extend_schema(
        summary="Delete a Group", description="Delete a group."
    ),
)
class GroupAdminViewSet(ModelViewSet):
    queryset = Group.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = GroupSerializer
