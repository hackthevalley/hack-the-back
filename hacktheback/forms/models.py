from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from ordered_model.models import OrderedModel

from hacktheback.core.models import (CreateTimestampMixin, FileMixin,
                                     GenericModel, IntervalMixin,
                                     TimestampMixin)
from hacktheback.forms.managers import FormManager


class Form(GenericModel, CreateTimestampMixin, IntervalMixin):
    """
    Multi-purpose form for hacker applications and miscellaneous use, managed
    by administrators.

    A form contains a set of :model: `forms.Question`s. Each :model:
    `forms.Response` is a response to a specific form.
    """

    class FormType(models.TextChoices):
        HACKER_APPLICATION = "HA", _("Hacker Application")
        MISCELLANEOUS = "MI", _("Miscellaneous")

    title = models.CharField(max_length=128)
    description = models.TextField()
    type = models.CharField(
        max_length=2, choices=FormType.choices, default=FormType.MISCELLANEOUS
    )
    is_draft = models.BooleanField(default=True)

    objects = FormManager()

    class Meta:
        ordering = ["-created_at"]


class Question(GenericModel, OrderedModel):
    """
    A question within a :model: `forms.Form`.

    Each answered question in a :model: `forms.Response` for a :model:
    `forms.Form` is an :model: `forms.Answer`.
    """

    class QuestionType(models.TextChoices):
        SHORT_TEXT = "SHORT_TEXT", _("Short Text")
        LONG_TEXT = "LONG_TEXT", _("Long Text")
        SELECT = "SELECT", _("Select")
        MULTISELECT = "MULTISELECT", _("Multiselect")
        RADIO = "RADIO", _("Radio")
        HTTP_URL = "HTTP_URL", _("HTTP URL")
        PHONE = "PHONE", _("Phone")
        EMAIL = "EMAIL", _("Email")
        PDF_FILE = "PDF_FILE", _("PDF File")
        IMAGE_FILE = "IMAGE_FILE", _("Image File")

    OPTION_TYPES = [
        QuestionType.SELECT,
        QuestionType.MULTISELECT,
        QuestionType.RADIO,
    ]
    SOLO_OPTION_TYPES = [QuestionType.SELECT, QuestionType.RADIO]
    NON_OPTION_TYPES = [
        QuestionType.SHORT_TEXT,
        QuestionType.LONG_TEXT,
        QuestionType.HTTP_URL,
        QuestionType.PHONE,
        QuestionType.EMAIL,
        QuestionType.PDF_FILE,
        QuestionType.IMAGE_FILE,
    ]
    FILE_TYPES = [QuestionType.PDF_FILE, QuestionType.IMAGE_FILE]

    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="questions"
    )
    label = models.CharField(max_length=128)
    type = models.CharField(
        max_length=11,
        choices=QuestionType.choices,
        default=QuestionType.SHORT_TEXT,
    )
    description = models.TextField(
        null=True, help_text="A question's help text."
    )
    placeholder = models.CharField(
        max_length=128,
        null=True,
        help_text="The value for a question's HTML placeholder.",
    )
    required = models.BooleanField(default=False)
    default_answer = models.TextField(null=True)

    order_with_respect_to = "form"

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["form", "label"], name="unique_question_per_form"
            )
        ]

    def __str__(self):
        return self.label


class QuestionOption(GenericModel, OrderedModel):
    """
    A selectable option for a :model: `forms.Question` that has an option
    type (Select, Multiselect, Radio).
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    label = models.CharField(max_length=128)
    default_answer = models.BooleanField(default=False)
    # TODO:
    # Edge case: If an admin deletes a QuestionOption but a related
    # AnswerOption exists, don't delete it but instead set this to True.
    persist_deletion = models.BooleanField(
        default=False,
        help_text="The option has been deleted and won't be valid for future "
        "responses.",
    )

    class Meta(OrderedModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["question", "label"], name="unique_option_per_question"
            )
        ]


class FormResponse(GenericModel, TimestampMixin):
    """
    A response to a related :model: `forms.Form`, by a :model: `account.User`.

    Each response has multiple :model: `forms.Answer`s for each :model:
    `forms.Question` in its related :model: `forms.Form`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="form_responses",
        null=True,
    )
    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="responses"
    )
    is_draft = models.BooleanField(default=True)
    admin_notes = models.TextField(null=True)

    class Meta:
        ordering = ["-updated_at"]


class Answer(GenericModel):
    """
    An answer to a :model: `forms.Question` in a :model: `forms.Form`, in which
    the :model: `forms.Form` has the answer's related :model: `forms.Response`.
    """

    # Only null when answer is for a question that is a selectable option or
    # if the question is not required
    answer = models.TextField(null=True)
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    response = models.ForeignKey(
        FormResponse,
        on_delete=models.CASCADE,
        related_name="answers",
    )


class AnswerOption(GenericModel):
    """
    The selected option as part of an :model: `forms.Answer`, where the :model:
    `forms.Answer` is for a :model: `form.Question` that has an option
    type (Select, Multiselect, Radio).
    """

    answer = models.ForeignKey(
        Answer, on_delete=models.CASCADE, related_name="answer_options"
    )
    option = models.ForeignKey(
        QuestionOption, on_delete=models.CASCADE, related_name="answers"
    )


class AnswerFile(GenericModel, FileMixin, CreateTimestampMixin):
    """
    A file that is uploaded by the user and its id can then be placed in
    the answer field of :model: `forms.Answer`.
    """

    FILE_UPLOAD_TO = settings.MEDIA_PATHS["ANSWER_FILE"]

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answer_files"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="answer_files",
        null=True,
    )


class HackathonApplicant(GenericModel, CreateTimestampMixin):
    """
    An applicant for the hackathon, where the applicant must be an existing
    :model: `account.User`.

    A HackathonApplicant should be created with a :model: `forms.Response`
    that is submitted for a hacker application :model: `forms.Form` for the
    related :model: `hackathon.Hackathon`.
    """

    class Status(models.TextChoices):
        APPLYING = "APPLYING", _("Applying")
        APPLIED = "APPLIED", _("Applied")
        UNDER_REVIEW = "UNDER_REVIEW", _("Under Review")
        WAITLISTED = "WAITLISTED", _("Waitlisted")
        ACCEPTED = "ACCEPTED", _("Accepted")
        REJECTED = "REJECTED", _("Rejected")
        ACCEPTED_INVITE = "ACCEPTED_INVITE", _("Accepted Invitation")
        REJECTED_INVITE = "REJECTED_INVITE", _("Rejected Invitation")
        SCANNED_IN = "SCANNED_IN", _("Scanned In")
        WALK_IN = "WALK_IN", _("Walked In")
        WALK_IN_SUBMIT = "WALK_IN_SUBMIT", _("Walked In (Submitted)")

    application = models.OneToOneField(
        FormResponse, on_delete=models.CASCADE, related_name="applicant"
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.APPLIED
    )

class Food(GenericModel):
    """
    Time periods for food serving
    """

    # Breakfast, lunch, dinner
    name = models.CharField(max_length=20)
    # hackathon day
    day = models.IntegerField()
    end_time = models.DateTimeField()

class HackerFoodTracking(GenericModel, CreateTimestampMixin):
    """
    A food event tracking table for the hackers
    """

    application = models.ForeignKey(
        FormResponse, on_delete=models.CASCADE, related_name="food"
    )
    serving = models.ForeignKey(
        Food, on_delete=models.CASCADE, related_name="servings"
    )

    class Meta:
        unique_together = ("application", "serving")
