
from django.http.response import FileResponse
from django.conf import settings
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.forms.models import HackathonApplicant
# from hacktheback.rest.permissions import AdminSiteModelPermissions

from .applepassgenerator.client import ApplePassGeneratorClient
from .applepassgenerator.models import EventTicket, BarcodeFormat, Barcode

@extend_schema(
    tags=["Hacker APIs", "Admin APIs", "Account"],
)
class DownloadApplePass(generics.GenericAPIView):
    queryset = HackathonApplicant.objects.all()
    permission_classes = []
    authorization_classes = []

    @extend_schema(summary="Generate apple pass for user")
    def get(self, request: Request) -> Response:
        hacker_id = request.query_params.get('id')

        applicant = HackathonApplicant.objects.get(id=hacker_id)
        user = applicant.application.user 

        if applicant.status not in [
            HackathonApplicant.Status.ACCEPTED,
            HackathonApplicant.Status.ACCEPTED_INVITE,
            HackathonApplicant.Status.SCANNED_IN,
            HackathonApplicant.Status.WALK_IN_SUBMIT,
        ]:
            return HttpResponse('not accepted, if you believe this is an error please contact an organizer or hello@hackthevalley.io', status=401)


        card_info = EventTicket()
        name = user.first_name + " " + user.last_name
        card_info.add_primary_field('name', name, 'Name')
        card_info.add_auxiliary_field('timing', 'Oct 4 10pm - Oct 6 10am', 'Duration')
        card_info.add_secondary_field('location', 'IC building, U of T Scarborough', 'Location')

        organization_name = "Hack the Valley"

        try:
            applepassgenerator_client = ApplePassGeneratorClient(
                team_identifier=settings.APPLE_TEAM_IDENTIFIER,
                pass_type_identifier=settings.APPLE_PASS_TYPE_IDENTIFIER,
                organization_name=organization_name,
            )
            apple_pass = applepassgenerator_client.get_pass(card_info)
            apple_pass.barcode = Barcode(hacker_id, format=BarcodeFormat.QR)
            apple_pass.description = "Hack the Valley"
            # apple_pass.logo_text = "Hack the Valley"
            apple_pass.serial_number = hacker_id
            apple_pass.background_color = 'rgb(25, 24, 32)'
            apple_pass.foreground_color = 'rgb(255, 255, 255)'
            apple_pass.label_color = 'rgb(255, 255, 255)'

            # Add logo/icon/strip image to file
            # apple_pass.add_file("background.png", open("images/thumbnail-90x90.png", "rb"))
            # apple_pass.add_file("background@2x.png", open("images/background@2x.png", "rb"))
            apple_pass.add_file("logo.png", open("images/logo-137x50.png", "rb"))
            # apple_pass.add_file("logo@2x.png", open("images/logo-50x50.png", "rb"))
            apple_pass.add_file("icon.png", open("images/icon-29x29.png", "rb"))
            # apple_pass.add_file("icon@2x.png", open("images/icon@2x.png", "rb"))
            apple_pass.add_file("thumbnail.png", open("images/thumbnail-90x90.png", "rb"))
            # apple_pass.add_file("thumbnail@2x.png", open("images/thumbnail-90x90.png", "rb"))

            
            file_bytes = apple_pass.create(
                certificate=settings.APPLE_WALLET_CERT_FILE,
                key=settings.APPLE_WALLET_KEY_FILE,
                wwdr_certificate=settings.APPLE_WWDR_CERT_FILE,
                password=settings.APPLE_WALLET_KEY_PASSWORD,
                zip_file=None
            )
        except Exception as e:
            return HttpResponse('error while generating pass: ' + str(e), status=500)

        file_bytes.seek(0)
        response = FileResponse(
            file_bytes,
            as_attachment=True,
            filename="htv.pkpass",
            content_type='application/vnd.apple.pkpass',
        )

        return response
