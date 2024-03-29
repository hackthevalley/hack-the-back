from datetime import datetime

from django.conf import settings
from drf_spectacular.utils import extend_schema
from graphql_jwt.utils import set_cookie
from rest_framework import generics, status
from rest_framework.response import Response

from hacktheback.rest.account.serializers import (
    JSONWebTokenBasicAuthSerializer,
    JSONWebTokenSocialAuthSerializer,
    RefreshJSONWebTokenSerializer,
    VerifyJSONWebTokenSerializer,
)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
class BaseJSONWebTokenAuthAPIView(generics.GenericAPIView):
    serializer_class = None
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        response = Response(serializer.validated_data)

        if settings.JWT_AUTH["JWT_COOKIE"]:
            set_cookie(
                response=response,
                key=settings.JWT_AUTH["JWT_COOKIE_NAME"],
                value=serializer.validated_data.get("token"),
                expires=datetime.utcnow()
                + settings.JWT_AUTH["JWT_EXPIRATION_DELTA"],
            )

        return response


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
class JSONWebTokenBasicAuthAPIView(BaseJSONWebTokenAuthAPIView):
    serializer_class = JSONWebTokenBasicAuthSerializer

    @extend_schema(
        summary="Create Auth Token from Basic Login"
    )
    def post(self, request, *args, **kwargs):
        """
        Authenticate a user with their email and password. Returns a JWT (JSON
        Web Token) to be used for authenticated requests on this server.
        """
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
class JSONWebTokenSocialAuthAPIView(BaseJSONWebTokenAuthAPIView):
    serializer_class = JSONWebTokenSocialAuthSerializer

    @extend_schema(
        summary="Create Auth Token from Social Login"
    )
    def post(self, request, *args, **kwargs):
        """
        Authenticate a user using an OAuth token from an authentication
        provider. Returns a JWT (JSON Web Token) to be used for authenticated
        requests on this server.
        """
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
class RefreshJSONWebTokenAPIView(BaseJSONWebTokenAuthAPIView):
    serializer_class = RefreshJSONWebTokenSerializer
    authentication_classes = []

    @extend_schema(summary="Refresh Auth Token")
    def post(self, request, *args, **kwargs):
        """
        Refresh a user authentication token (JWT).
        """
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Hacker APIs", "Admin APIs", "Account"])
class VerifyJSONWebTokenAPIView(generics.GenericAPIView):
    serializer_class = VerifyJSONWebTokenSerializer
    authentication_classes = []

    @extend_schema(summary="Verify Auth Token")
    def post(self, request, *args, **kwargs):
        """
        Confirm if a user authentication token (JWT) is valid.
        """
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(serializer.validated_data)
