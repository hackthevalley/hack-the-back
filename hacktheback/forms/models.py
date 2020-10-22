from django.db import models
from ordered_model.models import OrderedModel

from ..account.models import User
from ..core.models import (
    CreateTimestampMixin,
    GenericModel,
    IntervalMixin,
    TimestampMixin,
)
from ..hackathon.models import Hackathon


class Form(GenericModel, CreateTimestampMixin, IntervalMixin):
    """
    Multi-purpose form for hacker applications and miscellaneous use, managed
    by administrators.

    A form contains a set of :model: `forms.Question`s. Each :model:
    `forms.Response` is a response to a specific form.
    """

    HACKER_APPLICANT = "HA"
    MISCELLANEOUS = "MI"
    TYPE_CHOICES = [
        (HACKER_APPLICANT, "Hacker Applicant"),
        (MISCELLANEOUS, "Miscellaneous"),
    ]

    title = models.CharField(max_length=128)
    hackathon = models.ForeignKey(
        Hackathon, on_delete=models.CASCADE, related_name="forms"
    )
    description = models.TextField()
    type = models.CharField(
        max_length=2, choices=TYPE_CHOICES, default=MISCELLANEOUS
    )
    is_draft = models.BooleanField(default=True)


class Question(GenericModel, OrderedModel):
    """
    A question within a :model: `forms.Form`.

    Each answered question in a :model: `forms.Response` for a :model:
    `forms.Form` is an :model: `forms.Answer`.
    """

    SHORT_TEXT = "ST"
    LONG_TEXT = "LT"
    SELECT = "SL"
    MULTISELECT = "MS"
    HYPERLINK = "HL"
    PHONE = "PH"
    EMAIL = "EM"
    RADIO = "RD"
    FILE = "FL"
    TYPE_CHOICES = [
        (SHORT_TEXT, "Short Text"),
        (LONG_TEXT, "Long Text"),
        (SELECT, "Select"),
        (HYPERLINK, "Hyperlink"),
        (PHONE, "Phone"),
        (EMAIL, "Email"),
        (MULTISELECT, "Multiselect"),
        (RADIO, "Radio"),
        (FILE, "File"),
    ]

    OPTION_TYPES = [SELECT, MULTISELECT, RADIO]
    SOLO_OPTION_TYPES = [SELECT, RADIO]

    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="questions"
    )
    label = models.CharField(max_length=128)
    type = models.CharField(
        max_length=2, choices=TYPE_CHOICES, default=SHORT_TEXT
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
        unique_together = ["form", "label"]


class QuestionOption(GenericModel, OrderedModel):
    """
    A selectable option for a :model: `forms.Question` that has an option
    type (Select, Multiselect, Radio).
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    label = models.CharField(max_length=128)
    value = models.CharField(max_length=64)
    default_answer = models.BooleanField(default=False)
    # Edge case: If an admin deletes a QuestionOption but a related
    # AnswerOption exists, don't delete it but instead set this to True.
    persist_deletion = models.BooleanField(
        default=False,
        help_text="The option has been deleted and won't be valid for future responses.",
    )

    class Meta(OrderedModel.Meta):
        unique_together = ["question", "label"]


class Response(GenericModel, TimestampMixin):
    """
    A response to a related :model: `forms.Form`, by a :model: `account.User`.

    Each response has multiple :model: `forms.Answer`s for each :model:
    `forms.Question` in its related :model: `forms.Form`.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="form_responses"
    )
    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name="responses"
    )
    is_draft = models.BooleanField(default=True)


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
        Response,
        on_delete=models.CASCADE,
        related_name="responses",
    )


class AnswerOption(GenericModel):
    """
    The selected option as part of an :model: `forms.Answer`, where the :model:
    `forms.Answer` is for a :model: `form.Question` that has an option
    type (Select, Multiselect, Radio).
    """

    answer = models.ForeignKey(
        Answer, on_delete=models.CASCADE, related_name="selected_options"
    )
    option = models.ForeignKey(
        QuestionOption, on_delete=models.CASCADE, related_name="answers"
    )
