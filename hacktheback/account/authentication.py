from typing import Optional, Tuple

from django.utils.translation import ugettext as _
from graphql_jwt.exceptions import JSONWebTokenError, JSONWebTokenExpired
from graphql_jwt.utils import (
    get_http_authorization,
    get_payload,
    get_user_by_payload,
)
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request

from hacktheback.account.models import User


class JSONWebTokenAuthentication(BaseAuthentication):
    """
    Token based authentication using the JSON web token standard.

    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string specified in the setting
    `JWT_AUTH_HEADER_PREFIX`. For example:
        Authorization: JWT eyJhbGciOiAiSFMyNTYiLCAidHlwIj
    """

    def authenticate(self, request: Request) -> Optional[Tuple[User, dict]]:
        """
        Returns a tuple of `User` and a JSON web token if the signature for the
        token supplied in JWT-based authentication is valid. Otherwise, returns
        `None`.
        """
        jwt_value = get_http_authorization(request)
        if jwt_value is None:
            return None

        try:
            payload = get_payload(jwt_value)
        except (JSONWebTokenExpired, JSONWebTokenError) as e:
            raise exceptions.AuthenticationFailed(e.message)

        try:
            user = get_user_by_payload(payload)
        except JSONWebTokenError:
            raise exceptions.AuthenticationFailed(_("Invalid payload"))

        return user, payload
