# The MIT License (MIT)
#
# Copyright (c) 2013-2019 SUNSCRAPERS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from typing import Any

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import exceptions as django_exceptions
from django.core import serializers
from django.db import IntegrityError, transaction
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from graphql_jwt.exceptions import JSONWebTokenError, JSONWebTokenExpired
from graphql_jwt.settings import jwt_settings
from graphql_jwt.shortcuts import get_token
from graphql_jwt.utils import get_payload, get_user_by_payload
from rest_framework import exceptions, serializers
from rest_framework.exceptions import APIException, ValidationError
from social_core.exceptions import AuthException, MissingBackend
from social_django.utils import load_backend, load_strategy
from social_django.views import _do_login

from hacktheback.account import utils
from hacktheback.account.email import (
    ActivationEmail,
    ConfirmationEmail,
    PasswordChangedConfirmationEmail,
    PasswordResetEmail,
)

User = get_user_model()

jwt_payload_handler = jwt_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = jwt_settings.JWT_ENCODE_HANDLER
jwt_refresh_expired_handler = jwt_settings.JWT_REFRESH_EXPIRED_HANDLER


class BaseJSONWebTokenAuthSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)


class JSONWebTokenBasicAuthSerializer(BaseJSONWebTokenAuthSerializer):
    """
    Validate a username and password. Returns a JSON web token that can be
    used to authenticate later calls.
    """

    payload = serializers.JSONField(read_only=True)
    refresh_expires_in = serializers.IntegerField(read_only=True)

    @property
    def username_field(self) -> str:
        return User.USERNAME_FIELD

    def __init__(self, *args, **kwargs):
        """
        Dynamically add the username field to self.fields.
        """
        super().__init__(self, *args, **kwargs)

        self.fields[self.username_field] = serializers.CharField(
            write_only=True
        )
        self.fields["password"] = serializers.CharField(
            write_only=True, style={"input_type": "password"}
        )

    def validate(self, attrs):
        credentials = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
        }

        if attrs[self.username_field] and attrs["password"]:
            user = authenticate(**credentials)

            if user:
                if not user.is_active:
                    raise serializers.ValidationError(
                        _("User account is disabled.")
                    )

                payload = jwt_payload_handler(user)
                refresh_expires_in = (
                    payload["origIat"]
                    + jwt_settings.JWT_REFRESH_EXPIRATION_DELTA.total_seconds()
                )

                return {
                    "token": jwt_encode_handler(payload),
                    "payload": payload,
                    "refresh_expires_in": refresh_expires_in,
                }
            raise serializers.ValidationError(
                _("Please enter valid credentials")
            )
        else:
            raise serializers.ValidationError(
                _(f'Must include "{self.username_field}" and "password".')
            )


class JSONWebTokenSocialAuthSerializer(BaseJSONWebTokenAuthSerializer):
    """
    Validate an access token from a social provider. Returns a JSON web
    token that can be used to authenticate later calls.
    """

    provider = serializers.CharField(write_only=True)
    access_token = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    social = serializers.JSONField(read_only=True)

    def validate(self, attrs):
        request = self.context["request"]
        strategy = load_strategy(request)

        try:
            backend = load_backend(
                strategy, attrs["provider"], redirect_uri=None
            )
        except MissingBackend:
            raise serializers.ValidationError(_("Provider not found"))

        if request.user.is_authenticated:
            authenticated_user = request.user
        else:
            authenticated_user = None

        try:
            user = backend.do_auth(
                attrs["access_token"], user=authenticated_user
            )
        except AuthException as e:
            raise serializers.ValidationError(_(str(e)))

        if user is None:
            raise serializers.ValidationError(_("Invalid token"))

        user_model = strategy.storage.user.user_model()

        if not isinstance(user, user_model):
            raise serializers.ValidationError(
                _("`{}` is not a user instance").format(type(user).__name__)
            )

        _do_login(backend, user, user.social_user)

        return {
            "token": get_token(user),
            "social": {
                "id": user.social_user.id,
                "provider": user.social_user.provider,
                "uid": user.social_user.uid,
                "extraData": user.social_user.extra_data,
                "created": user.social_user.created,
                "modified": user.social_user.modified,
            },
        }


class RefreshJSONWebTokenSerializer(serializers.Serializer):
    token = serializers.CharField()
    payload = serializers.JSONField(read_only=True)
    refresh_expires_in = serializers.IntegerField(read_only=True)

    def validate(self, attrs):
        # Get and check payload
        try:
            payload = get_payload(attrs["token"])
        except (JSONWebTokenExpired, JSONWebTokenError) as e:
            raise serializers.ValidationError(str(e))

        # Get and check user by payload
        try:
            user = get_user_by_payload(payload)
        except JSONWebTokenError as e:
            raise serializers.ValidationError(str(e))
        # Get and check "origIat"
        orig_iat = payload.get("origIat")

        if not orig_iat:
            raise serializers.ValidationError(_("origIat field is required"))

        if jwt_refresh_expired_handler(orig_iat):
            raise serializers.ValidationError(_("Refresh has expired"))

        new_payload = jwt_payload_handler(user)
        new_payload["origIat"] = orig_iat
        refresh_expires_in = (
            orig_iat
            + jwt_settings.JWT_REFRESH_EXPIRATION_DELTA.total_seconds()
        )
        token = jwt_encode_handler(payload)

        return {
            "token": token,
            "payload": new_payload,
            "refresh_expires_in": refresh_expires_in,
        }


class VerifyJSONWebTokenSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)
    payload = serializers.JSONField(read_only=True)

    def validate(self, attrs):
        try:
            payload = get_payload(attrs["token"])
        except (JSONWebTokenExpired, JSONWebTokenError) as e:
            raise serializers.ValidationError(str(e))
        return {"payload": payload}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = tuple(User.REQUIRED_FIELDS) + (
            "id",
            User.USERNAME_FIELD,
        )
        read_only_fields = (User.USERNAME_FIELD,)

    def update(self, instance, validated_data):
        email_field = User.EMAIL_FIELD
        if settings.SEND_ACTIVATION_EMAIL and email_field in validated_data:
            instance_email = getattr(instance, email_field, None)
            if instance_email != validated_data[email_field]:
                instance.is_active = False
                instance.save(update_fields=["is_active"])
        return super().update(instance, validated_data)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )

    default_error_messages = {
        "cannot_create_user": "Unable to create account."
    }

    class Meta:
        model = User
        fields = tuple(User.REQUIRED_FIELDS) + (
            User.USERNAME_FIELD,
            "id",
            "password",
        )

    def validate(self, attrs):
        user = User(**attrs)
        password = attrs.get("password")

        try:
            validate_password(password, user)
        except django_exceptions.ValidationError as e:
            serializer_error = serializers.as_serializer_error(e)
            raise serializers.ValidationError(
                {"password": serializer_error["non_field_errors"]}
            )

        return attrs

    def create(self, validated_data):
        try:
            user = self.perform_create(validated_data)
        except IntegrityError:
            self.fail("cannot_create_user")

        return user

    def perform_create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(**validated_data)
            if settings.SEND_ACTIVATION_EMAIL:
                user.is_active = False
                user.save(update_fields=["is_active"])
        return user

    def save(self, request, **kwargs: Any):
        user = super().save()
        context = {"user": user}
        to = [utils.get_user_email(user)]
        if settings.SEND_ACTIVATION_EMAIL:
            ActivationEmail(request, context).send(to)
        elif settings.SEND_CONFIRMATION_EMAIL:
            ConfirmationEmail(request, context).send(to)
        return user


class UserCreatePasswordRetypeSerializer(UserCreateSerializer):
    default_error_messages = {
        "password_mismatch": "The two password fields didn't match."
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["re_password"] = serializers.CharField(
            style={"input_type": "password"}
        )

    def validate(self, attrs):
        self.fields.pop("re_password", None)
        re_password = attrs.pop("re_password")
        attrs = super().validate(attrs)
        if attrs["password"] == re_password:
            return attrs
        else:
            self.fail("password_mismatch")


class UserFunctionsMixin:
    def get_user(self, is_active=True):
        try:
            user = User._default_manager.get(
                is_active=is_active,
                **{self.email_field: self.data.get(self.email_field, "")},
            )
            if user.has_usable_password():
                return user
        except User.DoesNotExist:
            pass


class SendEmailResetSerializer(serializers.Serializer, UserFunctionsMixin):
    default_error_messages = {
        "email_not_found": "User with given email does not exist."
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.email_field = User.EMAIL_FIELD
        self.fields[self.email_field] = serializers.EmailField()

    def send(self, request):
        user = self.get_user()
        if user:
            context = {"user": user}
            to = [utils.get_user_email(user)]
            PasswordResetEmail(request, context).send(to)


class ResendActivationSerializer(SendEmailResetSerializer):
    def send(self, request):
        if not settings.SEND_ACTIVATION_EMAIL:
            raise APIException(detail=_("Account activation is not needed."))

        user = self.get_user(is_active=False)
        if not user:
            raise ValidationError(
                _("User has already been activated or does not exist.")
            )

        context = {"user": user}
        to = [utils.get_user_email(user)]
        ActivationEmail(request, context).send(to)


class UidAndTokenSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    default_error_messages = {
        "invalid_token": "Invalid token for given user.",
        "invalid_uid": "Invalid user id or user doesn't exist.",
    }

    def validate(self, attrs):
        validated_data = super().validate(attrs)

        # uid validation have to be here, because validate_<field_name>
        # doesn't work with modelserializer
        try:
            uid = utils.decode_uid(self.initial_data.get("uid", ""))
            self.user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            key_error = "invalid_uid"
            raise ValidationError(
                {"uid": [self.error_messages[key_error]]}, code=key_error
            )

        is_token_valid = default_token_generator.check_token(
            self.user, self.initial_data.get("token", "")
        )
        if is_token_valid:
            return validated_data
        else:
            key_error = "invalid_token"
            raise ValidationError(
                {"token": [self.error_messages[key_error]]}, code=key_error
            )


class ActivationSerializer(UidAndTokenSerializer):
    default_error_messages = {"stale_token": "Stale token for given user."}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not self.user.is_active:
            return attrs
        raise exceptions.PermissionDenied(self.error_messages["stale_token"])

    def save(self, request, **kwargs: Any):
        user = self.user
        user.is_active = True
        user.save()

        if settings.SEND_CONFIRMATION_EMAIL:
            context = {"user": user}
            to = [utils.get_user_email(user)]
            ConfirmationEmail(request, context).send(to)


class PasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(style={"input_type": "password"})

    def validate(self, attrs):
        user = (
            self.context
            and self.context["request"]
            and self.context["request"].user
        ) or self.user
        # why assert? There are ValidationError / fail everywhere
        assert user is not None

        try:
            validate_password(attrs["new_password"], user)
        except django_exceptions.ValidationError as e:
            raise serializers.ValidationError(
                {"new_password": list(e.messages)}
            )
        return super().validate(attrs)

    def save(self, request, **kwargs: Any):
        self.user.set_password(self.data["new_password"])
        if hasattr(self.user, "last_login"):
            self.user.last_login = now()
        self.user.save()

        if settings.PASSWORD_CHANGED_EMAIL_CONFIRMATION:
            context = {"user": self.user}
            to = [utils.get_user_email(self.user)]
            PasswordChangedConfirmationEmail(request, context).send(to)


class PasswordRetypeSerializer(PasswordSerializer):
    re_new_password = serializers.CharField(style={"input_type": "password"})

    default_error_messages = {
        "password_mismatch": "The two password fields didn't match."
    }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["new_password"] == attrs["re_new_password"]:
            return attrs
        else:
            self.fail("password_mismatch")


class CurrentPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(style={"input_type": "password"})

    default_error_messages = {"invalid_password": "Invalid password."}

    def validate_current_password(self, value):
        user = (
            self.context
            and self.context["request"]
            and self.context["request"].user
        ) or self.user
        # why assert? There are ValidationError / fail everywhere
        assert user is not None

        is_password_valid = user.check_password(value)
        if is_password_valid:
            return value
        else:
            self.fail("invalid_password")


class UsernameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (User.USERNAME_FIELD,)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username_field = User.USERNAME_FIELD
        self._default_username_field = User.USERNAME_FIELD
        self.fields["new_{}".format(self.username_field)] = self.fields.pop(
            self.username_field
        )

    def save(self, **kwargs):
        if self.username_field != self._default_username_field:
            kwargs[User.USERNAME_FIELD] = self.validated_data.get(
                "new_{}".format(self.username_field)
            )
        return super().save(**kwargs)


class UsernameRetypeSerializer(UsernameSerializer):
    default_error_messages = {
        "username_mismatch": f"The two {User.USERNAME_FIELD} fields didn't "
        f"match."
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["re_new_" + User.USERNAME_FIELD] = serializers.CharField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        new_username = attrs[User.USERNAME_FIELD]
        if new_username != attrs["re_new_{}".format(User.USERNAME_FIELD)]:
            self.fail("username_mismatch")
        else:
            return attrs


class SetPasswordRetypeSerializer(
    PasswordRetypeSerializer, CurrentPasswordSerializer
):
    pass


class PasswordResetConfirmRetypeSerializer(
    UidAndTokenSerializer, PasswordRetypeSerializer
):
    pass


class UsernameResetConfirmRetypeSerializer(
    UidAndTokenSerializer, UsernameRetypeSerializer
):
    pass


class SetUsernameSerializer(UsernameSerializer, CurrentPasswordSerializer):
    class Meta:
        model = User
        fields = (User.USERNAME_FIELD, "current_password")


class SetUsernameRetypeSerializer(
    SetUsernameSerializer, UsernameRetypeSerializer
):
    pass
