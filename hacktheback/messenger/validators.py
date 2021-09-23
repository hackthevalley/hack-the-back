from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from hacktheback.messenger.utils import render_mjml


def validate_mjml(value):
    rendered = render_mjml(value)
    if rendered is None:
        raise ValidationError(_("The value is not MJML."))
