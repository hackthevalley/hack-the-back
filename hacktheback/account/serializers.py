from django.contrib.auth import authenticate, get_user_model
from django.core import serializers
from django.utils.translation import ugettext as _
from graphql_jwt.exceptions import JSONWebTokenError, JSONWebTokenExpired
from graphql_jwt.settings import jwt_settings
from graphql_jwt.shortcuts import get_token
from graphql_jwt.utils import get_payload, get_user_by_payload
from rest_framework import serializers
from social_core.exceptions import AuthException, MissingBackend
from social_django.utils import load_backend, load_strategy
from social_django.views import _do_login

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
        return get_user_model().USERNAME_FIELD

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
