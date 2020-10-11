from django.db import models

from ..core.models import GenericModel


class BaseForm(GenericModel):
    """
    An abstract model of what form should have.
    """

    title = models.CharField(max_length=128)
    description = models.TextField()

    class Meta:
        abstract = True
