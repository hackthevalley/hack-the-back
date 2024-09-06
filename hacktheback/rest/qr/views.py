
import django.core.exceptions
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.forms.models import HackathonApplicant
from hacktheback.rest.forms.serializers import \
    HackerApplicationResponseAdminSerializer
from hacktheback.rest.permissions import AdminSiteModelPermissions

from .serializers import QrAdminSerializer


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


        if applicant.status not in [
            HackathonApplicant.Status.ACCEPTED_INVITE,
            HackathonApplicant.Status.ACCEPTED,
            HackathonApplicant.Status.SCANNED_IN,
            HackathonApplicant.Status.WALK_IN_SUBMIT
        ]:
            raise ValidationError(detail="Applicant was not accepted")

        message = "Applicant Checked In"

        if applicant.status == HackathonApplicant.Status.SCANNED_IN or applicant.status == HackathonApplicant.Status.WALK_IN:
            message = "Already Scanned In"
        elif applicant.status == HackathonApplicant.Status.ACCEPTED:
            message = "Applicant was accepted but did not RSVP"
            applicant.status = HackathonApplicant.Status.SCANNED_IN
            applicant.save()
        else:
            applicant.status = HackathonApplicant.Status.SCANNED_IN
            applicant.save()
        serializer = QrAdminSerializer(
            instance=applicant.application
        )
        scanned_count = HackathonApplicant.objects.filter(status=HackathonApplicant.Status.SCANNED_IN).count()
        return Response(data={"message": message, "body": serializer.data, "scanned_count": scanned_count})
