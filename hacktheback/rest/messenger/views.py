from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.renderers import StaticHTMLRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from hacktheback.messenger import utils
from hacktheback.messenger.models import EmailMessage, EmailTemplate, Message
from hacktheback.messenger.utils import render_mjml
from hacktheback.rest.messenger.serializers import (
    EmailTemplateRenderSerializer,
    EmailTemplateSerializer,
    MessageSerializer,
    SendEmailUsingTemplateInputSerializer,
)
from hacktheback.rest.pagination import StandardResultsPagination
from hacktheback.rest.permissions import AdminSiteModelPermissions

User = get_user_model()


@extend_schema(
    tags=["Admin APIs", "Messenger"],
)
@extend_schema_view(
    list=extend_schema(
        summary="List Email Templates",
        description="List all e-mail templates.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a Email Template",
        description="Retrieve an e-mail template.",
    ),
    create=extend_schema(
        summary="Create an Email Template",
        description="Create an e-mail template.",
    ),
    update=extend_schema(
        summary="Update an Email Template",
        description="Update an e-mail template.",
    ),
    partial_update=extend_schema(
        summary="Partial Update an Email Template",
        description="Partial update an e-mail template.",
    ),
    destroy=extend_schema(
        summary="Delete an Email Template",
        description="Delete an e-mail template.",
    ),
)
class EmailTemplateAdminViewSet(viewsets.ModelViewSet):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    pagination_class = StandardResultsPagination
    permission_classes = (AdminSiteModelPermissions,)


@extend_schema(
    tags=["Admin APIs", "Messenger"],
    request=EmailTemplateRenderSerializer,
    summary="Render MJML",
    responses={
        200: OpenApiResponse(description="Rendered HTML."),
        400: OpenApiResponse(description="Invalid MJML."),
    },
)
class RenderMJMLAdminAPIView(APIView):
    renderer_classes = [StaticHTMLRenderer]
    serializer_class = EmailTemplateRenderSerializer
    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        """
        Render MJML into HTML. All e-mails include a `user` variable that can
        be accessed via the template. Set `withExampleContext` to render the
        template with the context.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        mjml = serializer.validated_data.get("mjml")
        with_example_context = serializer.validated_data.get(
            "with_example_context"
        )
        context = None
        if with_example_context:
            context = {
                "user": User(
                    first_name="John",
                    last_name="Doe",
                    email="john.doe@example.com",
                    password="Password@123",
                )
            }
        html = render_mjml(mjml, context)
        if html is None:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(html)


@extend_schema(
    tags=["Admin APIs", "Messenger"],
)
@extend_schema_view(
    list=extend_schema(
        summary="List Messages",
        description="List all messages sent through the messenger app.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a Message",
        description="Retrieve a message sent through the messenger app.",
    ),
    update=extend_schema(
        summary="Update a Message",
        description="The sender's notes can only be updated.",
    ),
    partial_update=extend_schema(
        summary="Partial Update a Message",
        description="The sender's notes can only be updated.",
    ),
)
class MessageAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    pagination_class = StandardResultsPagination
    permission_classes = (AdminSiteModelPermissions,)


@extend_schema(
    tags=["Admin APIs", "Messenger"],
    request=SendEmailUsingTemplateInputSerializer,
    responses={200: MessageSerializer},
    summary="Send Email Using an Email Template",
)
class SendEmailUsingTemplateAdminAPIView(APIView):
    serializer_class = SendEmailUsingTemplateInputSerializer
    # TODO: Permission change
    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        """
        Send an e-mail to users using an existing e-mail template. The `from`
        email address is set as `DEFAULT_FROM_EMAIL` in the settings.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            template = data.get("template")
            recipients = data.get("recipients")
            subject = data.get("subject")
            is_test = data.get("is_test")
            sender_note = data.get("sender_note", None)

            # Get the historical instance of the latest email template
            hist_template = template.history.latest()
            # Create instances of Message and EmailMessage
            message = Message.objects.create(
                sender=request.user,
                sender_note=sender_note,
                is_test=is_test,
            )
            message.recipients.add(*recipients)
            EmailMessage.objects.create(
                subject=subject,
                template=hist_template,
                metadata=message,
            )
            plaintext = template.plaintext_message
            html = utils.render_mjml(template.html_message_as_mjml)
            # Send emails
            utils.send_emails(subject, recipients, plaintext, html)

        output_serializer = MessageSerializer(instance=message)
        return Response(output_serializer.data)
