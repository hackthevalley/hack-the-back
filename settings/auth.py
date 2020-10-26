import os

from django.utils.timezone import timedelta

from . import common, utils

# Custom User model
# https://docs.djangoproject.com/en/3.1/topics/auth/customizing/#substituting-a-custom-user-model

AUTH_USER_MODEL = "account.User"


# Django GraphQL JWT
# https://django-graphql-jwt.domake.io/en/latest/settings.html

GRAPHQL_JWT = {
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": timedelta(
        minutes=utils.get_int_environ("JWT_AUTH_EXPIRATION_DELTA_MINUTES", 30)
    ),
}


# Social Auth
# https://python-social-auth.readthedocs.io/

if not common.DEBUG:
    SOCIAL_AUTH_POSTGRES_JSONFIELD = True

SOCIAL_AUTH_USER_MODEL = "account.User"
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True
USER_FIELDS = ["email"]

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
