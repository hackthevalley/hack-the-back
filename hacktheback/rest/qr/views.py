from typing import Any

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.rest.account.serializers import (
    ActivationSerializer,
    PasswordResetConfirmRetypeSerializer,
    ResendActivationSerializer,
    SendEmailResetSerializer,
    UserCreatePasswordRetypeSerializer,
)


@extend_schema(
    tags=["Hacker APIs", "Admin APIs", "Account"], responses={204: None}
)
class QrAdmissionView(generics.GenericAPIView):
    authentication_classes = ()

    @extend_schema(summary="Admit user through QR")
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Validate a QR code
        """
        # serializer = self.get_serializer(data=request.data)
        # serializer.is_valid(raise_exception=True)
        # serializer.save(request=self.request)
        print(request.data)
        return Response(status=status.HTTP_204_NO_CONTENT)
