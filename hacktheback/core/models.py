import uuid

from django.db import models


class GenericModel(models.Model):
    # Note: Using UUIDs as primary keys with PostgreSQL will not create any
    # performance distruptions compared to other relational databases
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
