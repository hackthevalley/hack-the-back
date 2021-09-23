from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext as _
from simple_history.models import HistoricalRecords

from hacktheback.core.models import GenericModel, TimestampMixin
from hacktheback.messenger.validators import validate_mjml

User = get_user_model()


class EmailTemplate(TimestampMixin, GenericModel):
    """
    An e-mail template.
    """

    title = models.CharField(
        max_length=128,
        help_text=_(
            "The title of the template. This is not included in the template."
        ),
    )
    description = models.TextField(
        null=True,
        help_text=_(
            "The description of the template. This is not included in the "
            "template."
        ),
    )
    plaintext_message = models.TextField(
        null=True,
        help_text=_(
            "The plain-text alternative. It is important to have this as "
            "some e-mail clients won't render HTML e-mails."
        ),
    )
    html_message_as_mjml = models.TextField(
        validators=[validate_mjml],
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-updated_at"]


class Message(TimestampMixin, GenericModel):
    """
    A message sent to more than one recipient by one sender.
    """

    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
    )
    recipients = models.ManyToManyField(
        User,
        related_name="messages",
    )
    sender_note = models.TextField(
        null=True,
    )
    is_test = models.BooleanField(
        default=False,
    )

    class Meta:
        ordering = ["-created_at"]

    @property
    def type(self):
        """
        Returns the type of message.
        """
        if self.email is not None:
            return "EMAIL"
        return "UNDEFINED"


class EmailMessage(GenericModel):
    """
    An email message sent to more than one recipient by one sender.
    """

    subject = models.CharField(
        max_length=256,
    )
    template = models.ForeignKey(
        EmailTemplate.history.model,
        on_delete=models.SET_NULL,
        null=True,
    )
    metadata = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name="email",
    )
