import os
from datetime import timedelta

from django.contrib.auth import get_user_model

from . import common, utils

# Custom User model
# https://docs.djangoproject.com/en/3.2/topics/auth/customizing/#substituting-a-custom-user-model

AUTH_USER_MODEL = "account.User"


# JSON Web Tokens for REST and GraphQL requests
# https://django-graphql-jwt.domake.io/en/latest/settings.html

JWT_AUTH = {
    "JWT_ALGORITHM": "HS256",
    "JWT_AUDIENCE": None,
    "JWT_ISSUER": None,
    "JWT_LEEWAY": 0,
    "JWT_SECRET_KEY": common.SECRET_KEY,
    "JWT_PUBLIC_KEY": None,
    "JWT_PRIVATE_KEY": None,
    "JWT_VERIFY": True,
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": timedelta(seconds=60 * 5),  # 5 minutes
    "JWT_ALLOW_REFRESH": True,
    # https://django-graphql-jwt.domake.io/en/latest/refresh_token.html
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(days=7),  # 7 days
    "JWT_AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "JWT_AUTH_HEADER_PREFIX": "JWT",
    "JWT_ENCODE_HANDLER": "graphql_jwt.utils.jwt_encode",
    "JWT_DECODE_HANDLER": "graphql_jwt.utils.jwt_decode",
    # Custom payload structure for this project
    "JWT_PAYLOAD_HANDLER": "hacktheback.account.utils.jwt_payload",
    "JWT_PAYLOAD_GET_USERNAME_HANDLER": (
        lambda payload: payload.get(get_user_model().USERNAME_FIELD)
    ),
    "JWT_COOKIE": False,  # Specific to this project
    "JWT_COOKIE_NAME": "JWT",
    "JWT_REFRESH_TOKEN_COOKIE_NAME": "JWT-refresh-token",
    "JWT_COOKIE_SECURE": False,
    "JWT_COOKIE_PATH": "/",
    "JWT_COOKIE_DOMAIN": None,
    "JWT_COOKIE_SAMESITE": None,
}

# We use django-graphql-jwt to handle JSON web token logic
GRAPHQL_JWT = JWT_AUTH


# Social Auth
# https://python-social-auth.readthedocs.io/

if not common.DEBUG:
    SOCIAL_AUTH_POSTGRES_JSONFIELD = True

SOCIAL_AUTH_USER_MODEL = AUTH_USER_MODEL
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True
USER_FIELDS = ["email"]

# https://python-social-auth.readthedocs.io/en/stable/pipeline.html#authentication-pipeline
SOCIAL_AUTH_PIPELINE = (
    # Get the information we can about the user
    "social_core.pipeline.social_auth.social_details",
    # Get the social user id from whichever service we're authing thru
    "social_core.pipeline.social_auth.social_uid",
    # Verifies that the current auth process is valid within the current
    # project
    "social_core.pipeline.social_auth.auth_allowed",
    # Checks if the current social-account is already associated in the site.
    "social_core.pipeline.social_auth.social_user",
    # Make up a username for this person, appends a random string at the end if
    # there's any collision.
    "social_core.pipeline.user.get_username",
    # Send a validation email to the user to verify its email address.
    # Disabled by default.
    # 'social_core.pipeline.mail.mail_validation',
    # Associates the current social details with another user account with
    # a similar email address.
    "social_core.pipeline.social_auth.associate_by_email",
    # Create a user account if we haven't found one yet.
    "social_core.pipeline.user.create_user",
    # Create the record that associates the social account with the user.
    "social_core.pipeline.social_auth.associate_user",
    # Populate the extra_data field in the social record with the values
    # specified by settings (and the default ones like access_token, etc).
    "social_core.pipeline.social_auth.load_extra_data",
    # Update the user record with any changed info from the auth service.
    "social_core.pipeline.user.user_details",
)

SOCIAL_AUTH_BACKENDS = utils.get_list_environ("SOCIAL_AUTH_BACKENDS", [])

# Facebook (OAuth 2.0)
SOCIAL_AUTH_FACEBOOK_KEY = os.environ.get("SOCIAL_AUTH_FACEBOOK_KEY")
SOCIAL_AUTH_FACEBOOK_SECRET = os.environ.get("SOCIAL_AUTH_FACEBOOK_SECRET")
SOCIAL_AUTH_FACEBOOK_SCOPE = ["email"]
# Github (OAuth 2.0)
SOCIAL_AUTH_GITHUB_KEY = os.environ.get("SOCIAL_AUTH_GITHUB_KEY")
SOCIAL_AUTH_GITHUB_SECRET = os.environ.get("SOCIAL_AUTH_GITHUB_SECRET")
SOCIAL_AUTH_GITHUB_SCOPE = ["user:email"]
# Google (OAuth 2.0)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET"
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "https://www.googleapis.com/auth/userinfo.email"
]
# LinkedIn (OAuth 2.0)
SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY = os.environ.get(
    "SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY"
)
SOCIAL_AUTH_LINKEDIN_OAUTH2_SECRET = os.environ.get(
    "SOCIAL_AUTH_LINKEDIN_OAUTH2_SECRET"
)
SOCIAL_AUTH_LINKEDIN_OAUTH2_SCOPE = ["r_emailaddress"]
# Twitter (OAuth 2.0)
SOCIAL_AUTH_TWITTER_KEY = os.environ.get("SOCIAL_AUTH_TWITTER_KEY")
SOCIAL_AUTH_TWITTER_SECRET = os.environ.get("SOCIAL_AUTH_TWITTER_SECRET")

# For more authentication backend configurations, go to
# https://python-social-auth.readthedocs.io/en/latest/backends/index.html


# Authentication Backends
# https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#specifying-authentication-backends

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "graphql_jwt.backends.JSONWebTokenBackend",
] + SOCIAL_AUTH_BACKENDS
