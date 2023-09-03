from django.db import models

from hacktheback.core.models import GenericModel
from hacktheback.forms.models import HackathonApplicant


# Create your models here.
class QRCode(GenericModel):
    """
    Keep track of QR codes
    """

    hacker = models.ForeignKey(HackathonApplicant, on_delete=models.CASCADE)

    class Meta:
        ordering = []
