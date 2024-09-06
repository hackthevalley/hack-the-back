from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.account.models import User
from hacktheback.forms.models import Form, FormResponse, HackathonApplicant
from hacktheback.rest.forms.serializers import \
    HackerApplicationResponseSerializer
from hacktheback.rest.permissions import AdminSiteModelPermissions

from ....forms.utils import send_rsvp_email


class WalkInAdmissionAPIView(generics.GenericAPIView):
    permission_classes = (AdminSiteModelPermissions,)
    queryset = HackathonApplicant.objects.all()

    def post(self, request, *args, **kwargs) -> Response:
        assert "email" in request.data
        email = request.data.get("email")
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as not_found:
            raise NotFound(detail="User does not exist") from not_found
        try:
            applicant = HackathonApplicant.objects.get(application__user__email=email)
        except HackathonApplicant.DoesNotExist as not_found:
            form = Form.objects.filter(type=Form.FormType.HACKER_APPLICATION, is_draft=False).first()
            if not form:
                raise NotFound(detail="No open hacker application form available")
            form_response_data = {
                'user': str(user.id),
                'form': str(form.id),
                'is_draft': True,  # Assuming you want to create a submitted application
                'answers': [],
            }
            serializer = HackerApplicationResponseSerializer(context={'request': request, 'format': None, 'view': self, 'user': user}, data=form_response_data)
            serializer.is_valid(raise_exception=True)
            form_response = serializer.save()
            form_response.applicant.status = HackathonApplicant.Status.WALK_IN
            form_response.applicant.save()
            applicant = form_response.applicant
        if applicant.status in [
            HackathonApplicant.Status.ACCEPTED_INVITE,
            HackathonApplicant.Status.ACCEPTED,
            HackathonApplicant.Status.SCANNED_IN,
        ]:
          raise ValidationError(detail="Applicant already accepted")
        if applicant.status in [
            HackathonApplicant.Status.APPLYING
        ]:
          raise ValidationError(detail="Applicant not applied yet")
        else:
          applicant.status = HackathonApplicant.Status.WALK_IN
          applicant.save()
          send_rsvp_email(applicant.id, user.first_name, email)
        return Response(data={"success": True})