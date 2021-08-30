from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.rest.account.serializers import (
    SetPasswordRetypeSerializer,
    UserSerializer,
)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
class CurrentUserAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user

    @extend_schema(summary="Retrieve Current User Account")
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Retrieve the user that is currently signed in.
        """
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Update Current User Account")
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Update the user that is currently signed in.
        """
        return super().put(request, *args, **kwargs)

    @extend_schema(summary="Partial Update Current User Account")
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Partially update the user that is currently signed in.
        """
        return super().patch(request, *args, **kwargs)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"], responses={204: None})
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
