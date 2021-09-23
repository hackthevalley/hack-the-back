from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework import serializers

from hacktheback.messenger.models import EmailMessage, EmailTemplate, Message
from hacktheback.rest.account.serializers import UserSerializer

User = get_user_model()


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = (
            "id",
            "title",
            "description",
            "plaintext_message",
            "html_message_as_mjml",
        )


class EmailTemplateRenderSerializer(serializers.Serializer):
    mjml = serializers.CharField(
        write_only=True,
    )
    with_example_context = serializers.BooleanField(
        default=True,
        write_only=True,
    )


class EmailTemplateHistorySerializer(EmailTemplateSerializer):
    class Meta(EmailTemplateSerializer.Meta):
        model = EmailTemplate.history.model


class EmailMessageSerializer(serializers.ModelSerializer):
    template = EmailTemplateHistorySerializer()

    class Meta:
        model = EmailMessage
        fields = (
            "id",
            "subject",
            "template",
        )


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(
        read_only=True,
    )
    recipients = UserSerializer(
        read_only=True,
        many=True,
    )
    email = EmailMessageSerializer(
        read_only=True,
    )
    type = serializers.ChoiceField(
        read_only=True,
        choices=["EMAIL", "UNDEFINED"],
    )

    class Meta:
        model = Message
        fields = (
            "id",
            "type",
            "sender",
            "recipients",
            "sender_note",
            "is_test",
            "email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "type",
            "sender",
            "recipients",
            "is_test",
            "email",
            "created_at",
            "updated_at",
        )


class SendEmailUsingTemplateInputSerializer(serializers.Serializer):
    subject = serializers.CharField(
        write_only=True,
        max_length=256,
    )
    template = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=EmailTemplate.objects.all(),
    )
    recipients = serializers.PrimaryKeyRelatedField(
        write_only=True,
        queryset=User.objects.all(),
        many=True,
    )
    sender_note = serializers.CharField(
        write_only=True,
        allow_null=True,
        required=False,
    )
    is_test = serializers.BooleanField(
        write_only=True,
        default=False,
        help_text=_(
            "Warning: A message will be sent even if `is_test` is set to "
            "`True`."
        ),
    )
