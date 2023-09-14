
from django.contrib.auth import get_user_model
import django.core.exceptions
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response
from hacktheback.rest.permissions import AdminSiteModelPermissions
from hacktheback.forms.models import HackathonApplicant
from hacktheback.rest.forms.serializers import (
    HackerApplicationResponseAdminSerializer,
)
from .serializers import QrAdminSerializer
from rest_framework.exceptions import NotFound, ValidationError



@extend_schema(
    tags=["Hacker APIs", "Admin APIs", "Account"],
)
class QrAdmissionView(generics.GenericAPIView):
    queryset = HackathonApplicant.objects.all()
    permission_classes = (AdminSiteModelPermissions,)

    @extend_schema(summary="Admit user through QR")
    def post(self, request: Request) -> Response:
        """
        Validate a QR code
        must be in UUID format e.g.:
        "c2013f1a-c428-4ee9-8824-8f8fda7dd860"
        """
        assert "id" in request.data

        pk = request.data.get("id")
        try:
            applicant = self.queryset.get(pk=pk)
        except django.core.exceptions.ValidationError as invalid_uuid:
            raise ValidationError(detail="Not a valid QR code") from invalid_uuid
        except HackathonApplicant.DoesNotExist as not_found:
            raise NotFound(detail="Applicant does not exist") from not_found


        if (
            applicant.status != HackathonApplicant.Status.ACCEPTED_INVITE
            and applicant.status != HackathonApplicant.Status.ACCEPTED
            and applicant.status != HackathonApplicant.Status.SCANNED_IN
        ):
            raise ValidationError(detail="Applicant was not accepted")
    
        message = "Applicant Checked In"

        if applicant.status == HackathonApplicant.Status.SCANNED_IN:
            message = "Already Scanned In"
        else:
            applicant.status = HackathonApplicant.Status.SCANNED_IN
            applicant.save()
        serializer = QrAdminSerializer(
            instance=applicant.application
        )

        return Response(data={"message": message, "body": serializer.data})
