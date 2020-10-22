from django.db import models

from ..account.models import User
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

    APPLIED = "AP"
    UNDER_REVIEW = "UR"
    ACCEPTED = "AC"
    STATUS_TYPE_CHOICES = [
        (APPLIED, "Applied"),
        (UNDER_REVIEW, "Under Review"),
        (ACCEPTED, "Accepted"),
    ]

    MALE = "MA"
    FEMALE = "FM"
    PREFER_NOT_TO_SAY = "PS"
    GENDER_TYPE_CHOICES = [
        (MALE, "Male"),
        (FEMALE, "Female"),
        (PREFER_NOT_TO_SAY, "Prefer not to say"),
    ]

    hackathon = models.ForeignKey(
        Hackathon,
        on_delete=models.CASCADE,
        related_name="applicants",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=2, choices=STATUS_TYPE_CHOICES, default=APPLIED
    )
    gender = models.CharField(
        max_length=2, choices=GENDER_TYPE_CHOICES, default=PREFER_NOT_TO_SAY
    )
    school = models.CharField(max_length=256)
    year_of_graduation = models.CharField(max_length=4)
