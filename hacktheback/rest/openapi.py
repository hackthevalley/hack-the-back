from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JSONWebTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = (
        "hacktheback.account.authentication.JSONWebTokenAuthentication"
    )
    name = "JSONWebTokenAuthentication"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
        }
