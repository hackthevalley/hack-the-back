from typing import Any

from django.contrib.auth.models import Permission
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.rest.account.serializers import (
    PermissionSerializer,
    SetPasswordRetypeSerializer,
    UserSerializer,
)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
@extend_schema_view(
    get=extend_schema(
        summary="Retrieve Current User Account",
        description="Retrieve the user that is currently signed in.",
    ),
    put=extend_schema(
        summary="Update Current User Account",
        description="Update the user that is currently signed in.",
    ),
    patch=extend_schema(
        summary="Partial Update Current User Account",
        description="Partial update the user that is currently signed in.",
    ),
)
class CurrentUserAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


@extend_schema(
    tags=["Hacker APIs", "Admin APIs", "Account"], responses={204: None}
)
class CurrentUserSetPasswordAPIView(generics.GenericAPIView):
    serializer_class = SetPasswordRetypeSerializer
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(summary="Change Password for Current User Account")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Change the password of the user that is currently signed in.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.user = request.user
        serializer.is_valid(raise_exception=True)
        serializer.save(request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Hacker APIs", "Admin APIs", "Account"],
    summary="List Permissions for Current Admin User Account",
    description="List all permissions that the user that is currently signed "
    "in has. If the user is a superuser, then they have all permissions. If "
    "the user is in a group, they inherit all the permissions "
    "associated to that group.",
)
class CurrentUserPermissionsAPIView(generics.ListAPIView):
    serializer_class = PermissionSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)
    queryset = Permission.objects.none()

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Permission.objects.all()
        return Permission.objects.filter(Q(user=user) | Q(group__user=user))
