import graphene
from django.contrib.auth import get_user_model
from graphene_django_extras import DjangoInputObjectType

from hacktheback.account.serializers import (
    ActivationSerializer,
    PasswordResetConfirmRetypeSerializer,
    ResendActivationSerializer,
    SendEmailResetSerializer,
    UserCreatePasswordRetypeSerializer,
)
from hacktheback.core.errors import get_formatted_exception
from hacktheback.graphql.account.types.user import UserType
from hacktheback.graphql.core.errors import Errors

User = get_user_model()


class UserInput(DjangoInputObjectType):
    password = graphene.String(required=True)
    re_password = graphene.String(required=True)

    class Meta:
        model = User
        only_fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            "password",
            "re_password",
        )


class UidAndTokenInput(graphene.InputObjectType):
    uid = graphene.String(required=True)
    token = graphene.String(required=True)


class EmailInput(graphene.InputObjectType):
    email = graphene.String()


class ResetPasswordConfirmInput(UidAndTokenInput):
    new_password = graphene.String(required=True)
    re_new_password = graphene.String(required=True)


class UserCreate(graphene.Mutation):
    """
    Creates a new user. An activation e-mail is sent out to the new user if
    `settings.SEND_ACTIVATION_EMAIL` is set to `True`. Otherwise, a
    confirmation e-mail is sent out to the new user if
    `settings.SEND_CONFIRMATION_EMAIL` is set to `True`.
    """

    user = graphene.Field(UserType)
    errors = graphene.Field(Errors)

    class Arguments:
        input = UserInput(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        serializer = UserCreatePasswordRetypeSerializer(data=input)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return cls(user=None, errors=get_formatted_exception(e))
        return cls(user=serializer.save(request=info.context))


class UserActivation(graphene.Mutation):
    """
    Activate a user's account. A confirmation e-mail is sent out to the new
    user if `settings.SEND_CONFIRMATION_EMAIL` is set to `True`.
    """

    errors = graphene.Field(Errors)

    class Arguments:
        input = UidAndTokenInput(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        serializer = ActivationSerializer(data=input)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return cls(errors=get_formatted_exception(e))
        serializer.save(request=info.context)
        return cls()


class UserResendActivation(graphene.Mutation):
    """
    Resends a user account activation e-mail. Note that no e-mail would be sent
    if the user is already active or if they don’t have a usable password.
    Also if the sending of activation e-mails is disabled in settings, this
    call will result in 500 Internal Server Error.
    """

    errors = graphene.Field(Errors)

    class Arguments:
        input = EmailInput(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        serializer = ResendActivationSerializer(data=input)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.send(request=info.context)
        except Exception as e:
            return cls(errors=get_formatted_exception(e))
        return cls()


class UserResetPassword(graphene.Mutation):
    """
    Sends an e-mail to the specified user with a password reset link. Note that
    if the specified user doesn't exist, errors would still be `null`.
    """

    errors = graphene.Field(Errors)

    class Arguments:
        input = EmailInput(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        serializer = SendEmailResetSerializer(data=input)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.send(request=info.context)
        except Exception as e:
            return cls(errors=get_formatted_exception(e))
        return cls()


class UserResetPasswordConfirm(graphene.Mutation):
    """
    Last step in password reset process. Resets a user's password, provided
    that they give a valid token from the previous step of the password
    reset process. 400 Bad Request Error will be raised if the user has
    logged in or changed password since the token creation.
    """

    errors = graphene.Field(Errors)

    class Arguments:
        input = ResetPasswordConfirmInput(required=True)

    @classmethod
    def mutate(cls, root, info, input):
        serializer = PasswordResetConfirmRetypeSerializer(data=input)
        serializer.user = info.context.user
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save(request=info.context)
        except Exception as e:
            return cls(errors=get_formatted_exception(e))
        return cls()
