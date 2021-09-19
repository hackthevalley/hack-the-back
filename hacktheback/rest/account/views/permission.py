from django.contrib.auth.models import Permission
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ReadOnlyModelViewSet

from hacktheback.rest.account.serializers import PermissionSerializer
from hacktheback.rest.permissions import AdminSiteModelPermissions


@extend_schema(tags=["Admin APIs", "Account"])
@extend_schema_view(
    list=extend_schema(
        summary="List Permissions",
        description="List permissions that an admin user can have.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a Permission",
        description="Retrieve a permission that an admin user can have.",
    ),
)
class PermissionAdminViewSet(ReadOnlyModelViewSet):
    queryset = Permission.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = PermissionSerializer
