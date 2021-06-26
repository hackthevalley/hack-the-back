from typing import Any

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.account.serializers import (
    ActivationSerializer,
    PasswordResetConfirmRetypeSerializer,
    ResendActivationSerializer,
    SendEmailResetSerializer,
    UserCreatePasswordRetypeSerializer,
)

User = get_user_model()


@extend_schema(tags=["Account"])
class UserAPIView(generics.CreateAPIView):
    serializer_class = UserCreatePasswordRetypeSerializer
    authentication_classes = ()

    @extend_schema(summary="Register User Account")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Creates a new user. An activation e-mail is sent out to the new user
        if `settings.SEND_ACTIVATION_EMAIL` is set to `True`. Otherwise, a
        confirmation e-mail is sent out to the new user if
        `settings.SEND_CONFIRMATION_EMAIL` is set to `True`.
        """
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(request=self.request)


@extend_schema(tags=["Account"], responses={204: None})
class UserActivationAPIView(generics.GenericAPIView):
    serializer_class = ActivationSerializer
    authentication_classes = ()

    @extend_schema(summary="Activate User Account")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Activate a user's account. A confirmation e-mail is sent out to the new
        user if `settings.SEND_CONFIRMATION_EMAIL` is set to `True`.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(request=self.request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Account"], responses={204: None})
class UserResendActivationAPIView(generics.GenericAPIView):
    serializer_class = ResendActivationSerializer
    authentication_classes = ()

    @extend_schema(summary="Resend User Account Activation E-mail")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Resends a user account activation e-mail. Note that no e-mail would be
        sent if the user is already active or if they don’t have a usable
        password. Also if the sending of activation e-mails is disabled in
        settings, this call will result in 500 Internal Server Error.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.send(request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Account"], responses={204: None})
class UserResetPasswordAPIView(generics.GenericAPIView):
    serializer_class = SendEmailResetSerializer
    authentication_classes = ()

    @extend_schema(summary="Reset Password for User Account (Step 1)")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Sends a password reset link in an e-mail to the user with the specified
        e-mail address. Note that if a user with the specified e-mail address
        doesn't exist, no error would be provided.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.send(request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Account"], responses={204: None})
class UserResetPasswordConfirmAPIView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmRetypeSerializer
    authentication_classes = ()

    @extend_schema(summary="Reset Password for User Account (Step 2)")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Last step in password reset process. Resets a user's password, provided
        that they give a valid token from the previous step of the password
        reset process. 400 Bad Request Error will be raised if the user has
        logged in or changed password since the token creation.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
