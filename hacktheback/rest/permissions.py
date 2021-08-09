from typing import Any

from rest_framework import permissions, views
from rest_framework.request import Request


class IsOwner(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to access it.
    """

    def has_object_permission(
        self, request: Request, view: views.APIView, obj: Any
    ) -> bool:
        return obj.user == request.user
