import os
import uuid
from datetime import timedelta
from email.utils import getaddresses

import environ
from django.contrib.auth import get_user_model

# WARNING: You should not directly edit this file if you are configuring
# your application. Instead, it is recommended that you configure your
# application through environment variables. This project uses `Django-environ`
# to load environment variables and cast them accordingly to update settings.

# Helpful links:
# 1. Deployment Checklist
# --> https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/
# 2. Installation Wiki (includes detailed list of Environment Variables)
# --> https://github.com/hackthevalley/hack-the-back/wiki/Installation

# ------

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

env = environ.Env()
# Read .env file into os.environ, if exists
environ.Env.read_env(env_file=os.path.join(PROJECT_ROOT, ".env"))

# --- Settings ---

SITE_NAME = env.str("SITE_NAME", default="Hack the Back")

# --- RSVP Email Template Settings ---
EVENT_START = "October 14th"
EVENT_END = "16th"
RSVP_DUE = "October 10th"

# SECURITY WARNING: Don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

# SECURITY WARNING: Keep the secret key used in production a secret!
SECRET_KEY = env.str("SECRET_KEY")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

DATABASE_CONFIG = None
if DEBUG and not env.bool("DEBUG_AS_PRODUCTION", default=False) and ("DATABASE_URL" not in env):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(PROJECT_ROOT, "db.sqlite3"),
        }
    }
else:
    DATABASE_CONFIG = env.db("DATABASE_URL")
    DATABASES = {"default": DATABASE_CONFIG}

if DEBUG and not env.bool("DEBUG_AS_PRODUCTION", default=False):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_CONFIG = env.email_url("EMAIL_URL")
    vars().update(EMAIL_CONFIG)

TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_L10N = True
USE_TZ = True

WSGI_APPLICATION = "hacktheback.wsgi.application"

ROOT_URLCONF = "hacktheback.urls"

STATIC_ROOT = os.path.join(PROJECT_ROOT, "static")
STATIC_URL = env.str("STATIC_URL", default="/static/")


def media_upload_to_path(instance, filename, sub_dir=None):
    upload_dir = (
        f"user_{'anonymous' if instance.user.id is None else instance.user.id}"
    )
    file_ext = filename.split(".")[-1].lower()
    new_filename = f"{uuid.uuid4()}.{file_ext}"
    if sub_dir is None:
        return os.path.join(upload_dir, new_filename)
    return os.path.join(upload_dir, sub_dir, new_filename)



MEDIA_MAX_FILE_SIZE = env.int("MEDIA_MAX_FILE_SIZE", 52428800)
MEDIA_ROOT = os.path.join(PROJECT_ROOT, "media")
MEDIA_URL = env.str("MEDIA_URL", default="/media/")

MEDIA_PATHS = {
    "ANSWER_FILE": lambda _, instance, filename: media_upload_to_path(
        instance, filename, "form"
    ),
    "QR_CODES": os.path.join(MEDIA_ROOT, "qr_code")
}

ADMINS = getaddresses([env.str("ADMINS", "")])

DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", "webmaster@localhost")

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_USER_MODEL = "account.User"

INSTALLED_APPS = [
    # Django modules
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "hacktheback.account",
    "hacktheback.core",
    "hacktheback.forms",
    "hacktheback.graphql",
    "hacktheback.messenger",
    "hacktheback.rest",
    # External apps
    "django_filters",
    "drf_spectacular",
    "graphene_django",
    "phonenumber_field",
    "rest_framework",
    "simple_history",
    "social_django",
    "corsheaders",
    "qrcode"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation"
        ".UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation"
        ".MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation"
        ".CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation"
        ".NumericPasswordValidator",
    },
]

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:4200",
    ],
)

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "hacktheback.account.authentication.JSONWebTokenAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
    "EXCEPTION_HANDLER": "hacktheback.core.errors.exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": SITE_NAME,
    "DESCRIPTION": "RESTful APIs for managing a Hackathon. To use the GraphQL "
    "API instead, head over the playground at [/api/graphql]("
    "/api/graphql).",
    "VERSION": "1.0.0",
    "TAGS": [
        {
            "name": "Hacker APIs",
            "description": "**All operations for hacker users.**",
        },
        {
            "name": "Admin APIs",
            "description": "**All operations for admin users.**",
        },
        {
            "name": "Account",
            "description": "Operations associated with the `account` app. "
            "_This includes operations for all users._",
        },
        {
            "name": "Forms",
            "description": "Operations associated with the `forms` app. "
            "_This includes operations for all users._",
        },
        {
            "name": "Messenger",
            "description": "Operations associated with the `messenger` app.",
        },
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "docExpansion": "none",
    },
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.contrib.djangorestframework_camel_case"
        ".camelize_serializer_fields",
    ],
}

GRAPHENE = {
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
    ],
}

JWT_EXPIRATION_DELTA = env.int("JWT_EXPIRATION", default=60 * 5)
JWT_REFRESH_EXPIRATION_DELTA = env.int(
    "JWT_REFRESH_EXPIRATION", default=60 * 60 * 24 * 7
)
JWT_AUTH_HEADER_PREFIX = env.str("JWT_AUTH_HEADER_PREFIX", "JWT")
JWT_AUTH = {
    "JWT_ALGORITHM": "HS256",
    "JWT_AUDIENCE": None,
    "JWT_ISSUER": None,
    "JWT_LEEWAY": 0,
    "JWT_SECRET_KEY": SECRET_KEY,
    "JWT_PUBLIC_KEY": None,
    "JWT_PRIVATE_KEY": None,
    "JWT_VERIFY": True,
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_EXPIRATION_DELTA": timedelta(seconds=JWT_EXPIRATION_DELTA),
    "JWT_ALLOW_REFRESH": True,
    # https://django-graphql-jwt.domake.io/en/latest/refresh_token.html
    "JWT_REFRESH_EXPIRATION_DELTA": timedelta(
        days=JWT_REFRESH_EXPIRATION_DELTA
    ),
    "JWT_AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "JWT_AUTH_HEADER_PREFIX": JWT_AUTH_HEADER_PREFIX,
    "JWT_ENCODE_HANDLER": "graphql_jwt.utils.jwt_encode",
    "JWT_DECODE_HANDLER": "graphql_jwt.utils.jwt_decode",
    # Custom payload structure for this project
    "JWT_PAYLOAD_HANDLER": "hacktheback.account.utils.jwt_payload",
    "JWT_PAYLOAD_GET_USERNAME_HANDLER": (
        lambda payload: payload.get(get_user_model().USERNAME_FIELD)
    ),
    # TODO: Allow cookies for auth in this project
    "JWT_COOKIE": False,
    "JWT_COOKIE_NAME": "JWT",
    "JWT_REFRESH_TOKEN_COOKIE_NAME": "JWT-refresh-token",
    "JWT_COOKIE_SECURE": False,
    "JWT_COOKIE_PATH": "/",
    "JWT_COOKIE_DOMAIN": None,
    "JWT_COOKIE_SAMESITE": None,
}
GRAPHQL_JWT = JWT_AUTH

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
if DATABASE_CONFIG and "postgresql" in DATABASE_CONFIG.get("ENGINE"):
    # TODO: Test this with postgres database
    SOCIAL_AUTH_POSTGRES_JSONFIELD = True
SOCIAL_AUTH_USER_MODEL = AUTH_USER_MODEL
SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL = True
USER_FIELDS = ["email"]
SOCIAL_AUTH_BACKENDS = env.list("SOCIAL_AUTH_BACKENDS", default=[])
if "social_core.backends.facebook.FacebookOAuth2" in SOCIAL_AUTH_BACKENDS:
    SOCIAL_AUTH_FACEBOOK_KEY = env.str("SOCIAL_AUTH_FACEBOOK_KEY")
    SOCIAL_AUTH_FACEBOOK_SECRET = env.str("SOCIAL_AUTH_FACEBOOK_SECRET")
    SOCIAL_AUTH_FACEBOOK_SCOPE = ["email"]
if "social_core.backends.github.GithubOAuth2" in SOCIAL_AUTH_BACKENDS:
    SOCIAL_AUTH_GITHUB_KEY = env.str("SOCIAL_AUTH_GITHUB_KEY")
    SOCIAL_AUTH_GITHUB_SECRET = env.str("SOCIAL_AUTH_GITHUB_SECRET")
    SOCIAL_AUTH_GITHUB_SCOPE = ["user:email"]
if "social_core.backends.google.GoogleOAuth2" in SOCIAL_AUTH_BACKENDS:
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env.str("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY")
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env.str(
        "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET"
    )
    SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
        "https://www.googleapis.com/auth/userinfo.email"
    ]
if "social_core.backends.linkedin.LinkedinOAuth2" in SOCIAL_AUTH_BACKENDS:
    SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY = env.str(
        "SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY"
    )
    SOCIAL_AUTH_LINKEDIN_OAUTH2_SECRET = env.str(
        "SOCIAL_AUTH_LINKEDIN_OAUTH2_SECRET"
    )
    SOCIAL_AUTH_LINKEDIN_OAUTH2_SCOPE = ["r_emailaddress"]
if "social_core.backends.twitter.TwitterOAuth" in SOCIAL_AUTH_BACKENDS:
    SOCIAL_AUTH_TWITTER_KEY = env.str("SOCIAL_AUTH_TWITTER_KEY")
    SOCIAL_AUTH_TWITTER_SECRET = env.str("SOCIAL_AUTH_TWITTER_SECRET")

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "graphql_jwt.backends.JSONWebTokenBackend",
] + SOCIAL_AUTH_BACKENDS

SEND_ACTIVATION_EMAIL = env.bool("SEND_ACTIVATION_EMAIL", default=True)
ACTIVATION_URL = env.str(
    "ACTIVATION_URL", default="activate?uid={uid}&token={token}"
)
SEND_CONFIRMATION_EMAIL = env.bool("SEND_CONFIRMATION_EMAIL", default=True)
PASSWORD_RESET_CONFIRM_URL = env.str(
    "PASSWORD_RESET_CONFIRM_URL",
    default="reset_password?uid={uid}&token={token}",
)
PASSWORD_CHANGED_EMAIL_CONFIRMATION = env.bool(
    "PASSWORD_CHANGED_EMAIL_CONFIRMATION", default=True
)

MJML_API_URL = env.str("MJML_API_URL", default="https://api.mjml.io/v1/render")
MJML_APPLICATION_ID = env.str("MJML_APPLICATION_ID")
MJML_SECRET_KEY = env.str("MJML_SECRET_KEY")
