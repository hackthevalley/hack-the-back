import graphene
from django.contrib.auth import get_user_model
from graphene_django_extras import DjangoInputObjectType
from graphql_jwt.decorators import login_required

from hacktheback.core.errors import get_formatted_exception
from hacktheback.graphql.account.types.user import UserType
from hacktheback.graphql.core.errors import Errors
from hacktheback.rest.account.serializers import (
    SetPasswordRetypeSerializer,
    UserSerializer,
)

User = get_user_model()


class CurrentUserInput(DjangoInputObjectType):
    class Meta:
        model = User
        only_fields = tuple(User.REQUIRED_FIELDS)


class SetPasswordInput(graphene.InputObjectType):
    new_password = graphene.String(required=True)
    re_new_password = graphene.String(required=True)
    current_password = graphene.String(required=True)


class CurrentUserUpdate(graphene.Mutation):
    """
    Update the user that is currently signed in.
    """

    user = graphene.Field(UserType)
    errors = graphene.Field(Errors)

    class Arguments:
        input = CurrentUserInput(required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, input):
        user = info.context.user
        serializer = UserSerializer(user, data=input, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return cls(user=None, errors=get_formatted_exception(e))
        return cls(user=serializer.save())


class CurrentUserSetPassword(graphene.Mutation):
    """
    Change the password of the user that is currently signed in.
    """

    errors = graphene.Field(Errors)

    class Arguments:
        input = SetPasswordInput(required=True)

    @classmethod
    @login_required
    def mutate(cls, root, info, input):
        serializer = SetPasswordRetypeSerializer(data=input)
        serializer.user = info.context.user
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save(request=info.context)
        except Exception as e:
            return cls(errors=get_formatted_exception(e))
        return cls()
