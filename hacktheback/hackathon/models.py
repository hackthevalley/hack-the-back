from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from ..core.models import CreateTimestampMixin, GenericModel, IntervalMixin


class Hackathon(GenericModel, IntervalMixin, CreateTimestampMixin):
    """
    A Hackathon event. Most items are grouped under a Hackathon.
    """

    name = models.CharField(max_length=128)


class HackathonApplicant(GenericModel, CreateTimestampMixin):
    """
    An applicant for a :model: `hackathon.Hackathon`, where the applicant must
    be an existing :model: `account.User`.

    A HackathonApplicant should be created with a :model: `forms.Response`
    that is submitted for a hacker application :model: `forms.Form` for the
    related :model: `hackathon.Hackathon`.
    """

    class Status(models.TextChoices):
        APPLIED = "AP", _("Applied")
        UNDER_REVIEW = "UR", _("Under Review")
        ACCEPTED = "AC", _("Accepted")

    class Gender(models.TextChoices):
        MALE = "MA", _("Male")
        FEMAILE = "FM", _("Female")
        PREFER_NOT_TO_SAY = "PS", _("Prefer not to say")

    hackathon = models.ForeignKey(
        Hackathon,
        on_delete=models.CASCADE,
        related_name="applicants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=2, choices=Status.choices, default=Status.APPLIED
    )
    gender = models.CharField(
        max_length=2, choices=Gender.choices, default=Gender.PREFER_NOT_TO_SAY
    )
    school = models.CharField(max_length=256)
    year_of_graduation = models.CharField(max_length=4)
