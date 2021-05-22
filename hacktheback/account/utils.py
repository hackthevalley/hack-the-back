from calendar import timegm
from datetime import datetime

from django.conf import settings

from hacktheback.account.models import User


def jwt_payload(user: User, context=None) -> dict:
    """Returns the payload for a JSON web token."""

    exp = datetime.utcnow() + settings.JWT_AUTH["JWT_EXPIRATION_DELTA"]

    payload = {
        # By default, username_field = "email"
        user.USERNAME_FIELD: user.get_username(),
        "fullName": user.get_full_name(),
        "firstName": user.first_name,
        "lastName": user.last_name,
        "exp": timegm(exp.utctimetuple()),
    }

    if settings.JWT_AUTH["JWT_ALLOW_REFRESH"]:
        payload["origIat"] = timegm(datetime.utcnow().utctimetuple())

    if settings.JWT_AUTH["JWT_AUDIENCE"] is not None:
        payload["aud"] = settings.JWT_AUTH["JWT_AUDIENCE"]

    if settings.JWT_AUTH["JWT_ISSUER"] is not None:
        payload["iss"] = settings.JWT_AUTH["JWT_ISSUER"]

    return payload
