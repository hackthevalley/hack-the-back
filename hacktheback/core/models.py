import uuid

from django.db import models


class GenericModel(models.Model):
    """
    This abstract model should be inherited by all models in this project such
    that all models use a UUID for the primary key instead of an
    auto-incremented value.
    """

    # Note: Using UUIDs as primary keys with PostgreSQL will not create any
    # performance distruptions compared to other relational databases
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
    This abstract model should be inherited by models that require an updation
    timestamp.
    """

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TimestampMixin(CreateTimestampMixin, UpdateTimestampMixin):
    """
    This abstract model should be inherited by models that require a creation
    and an updation timestamp.
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
