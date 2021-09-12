from typing import Any

from rest_framework.permissions import BasePermission, DjangoModelPermissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwner(BasePermission):
    """
    Object-level permission to only allow owners of an object to access it.
    """

    def has_object_permission(
        self, request: Request, view: APIView, obj: Any
    ) -> bool:
        return obj.user == request.user


class AdminSiteModelPermissions(DjangoModelPermissions):
    """
    Ensures that the user is authenticated, the user can access the admin site
    and has the appropriate `view`/`add`/`change`/`delete` permissions on the
    model.

    This permission can only be applied against view classes that provide a
    `.queryset` attribute.
    """

    perms_map = {
        "OPTIONS": [],
        "HEAD": [],
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request: Request, view: APIView) -> bool:
        is_admin = bool(request.user and request.user.is_staff)
        has_strict_model_permissions = super().has_permission(request, view)
        return is_admin and has_strict_model_permissions


__all__ = [
    "IsOwner",
    "AdminSiteModelPermissions",
]
