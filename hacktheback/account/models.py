from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from hacktheback.account.managers import UserManager
from hacktheback.core.models import GenericModel


class User(AbstractUser, GenericModel):
    username = None
    email = models.EmailField("email address", unique=True)
    phone_number = PhoneNumberField()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["email"]
