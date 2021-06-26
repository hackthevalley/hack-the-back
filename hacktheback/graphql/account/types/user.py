from django.contrib.auth import get_user_model
from graphene_django import DjangoObjectType

from hacktheback.account.serializers import UserSerializer

User = get_user_model()


class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = UserSerializer.Meta.fields
