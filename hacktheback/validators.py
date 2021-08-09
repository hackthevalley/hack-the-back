from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from hurry.filesize import alternative, size


def validate_file_size(value):
    max_size = settings.MEDIA_MAX_FILE_SIZE
    if value.size > max_size:
        raise ValidationError(
            _(
                "The maximum file size that can be uploaded is %(max_size)s. "
                "Your file's size is %(size)s."
            )
            % {
                "max_size": size(max_size, system=alternative),
                "size": size(value.size, system=alternative),
            }
        )
