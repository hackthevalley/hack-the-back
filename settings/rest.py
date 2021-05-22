# REST API Settings

# Django Rest Framework (DRF)

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
        "djangorestframework_camel_case.render.CamelCaseBrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "hacktheback.account.authentication.JSONWebTokenAuthentication",
    ),
}

# DRF Spectacular

SPECTACULAR_SETTINGS = {
    "TITLE": "Hack the Back",
    "DESCRIPTION": "RESTful APIs for managing Hackathons. To use the GraphQL "
    "API instead, head over the playground at [/api/graphql]("
    "/api/graphql).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CAMELIZE_NAMES": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.contrib.djangorestframework_camel_case"
        ".camelize_serializer_fields",
    ],
}
