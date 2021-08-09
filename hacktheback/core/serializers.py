from rest_framework.exceptions import ValidationError
from rest_framework.fields import MISSING_ERROR_MESSAGE


class ValidationMixin:
    def __init__(self, *args, **kwargs):
        self.field_error_messages = dict()
        super().__init__(*args, **kwargs)

    def fail_for_field(self, key, **kwargs):
        """
        A helper method that simply raises a validation error for a field.
        """
        try:
            field, msg = self.field_error_messages[key]
        except KeyError:
            class_name = self.__class__.__name__
            msg = MISSING_ERROR_MESSAGE.format(class_name=class_name, key=key)
            raise AssertionError(msg)
        message_string = msg.format(**kwargs)
        message = {field: message_string}
        raise ValidationError(message, code=key)
