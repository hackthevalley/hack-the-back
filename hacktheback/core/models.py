import uuid

from django.conf import settings
from django.db import models

from hacktheback.validators import validate_file_size


class GenericModel(models.Model):
    """
    This abstract model should be inherited by all models in this project such
    that all models use a UUID for the primary key instead of an
    auto-incremented value.
    """

    # Note: Using UUIDs as primary keys with PostgreSQL will not create any
    # performance disruptions compared to other relational databases
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class CreateTimestampMixin(models.Model):
    """
    This abstract model should be inherited by models that require a creation
    timestamp.
    """

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdateTimestampMixin(models.Model):
    """
    This abstract model should be inherited by models that require an update at
    timestamp.
    """

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimestampMixin(CreateTimestampMixin, UpdateTimestampMixin):
    """
    This abstract model should be inherited by models that require a creation
    and an update at timestamp.
    """

    class Meta:
        abstract = True


class IntervalMixin(models.Model):
    """
    This abstract model should be inherited by models that require a start and
    end time.
    """

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    class Meta:
        abstract = True


def file_upload_to(instance, filename):
    return instance.FILE_UPLOAD_TO(instance, filename)


class FileMixin(models.Model):
    """
    This abstract model should be inherited by models that require a file to
    be uploaded. When saving a file, the original_filename field must be
    filled in with the file name upon upload.
    """

    FILE_UPLOAD_TO = ""

    file = models.FileField(
        null=False,
        upload_to=file_upload_to,
        validators=[validate_file_size],
    )
    original_filename = models.CharField(max_length=260)

    class Meta:
        abstract = True
