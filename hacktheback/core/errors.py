from django.http.response import Http404
from hipo_drf_exceptions import handler as hipo_handler
from rest_framework.exceptions import APIException


def exception_handler(exc, context):
    """
    Custom exception handler for REST API views.
    """
    response = hipo_handler(exc, context)

    if response and response.data:
        data = response.data
        field_errors = []
        non_field_errors = []
        if data.get("detail"):
            for field, errors in data["detail"].items():
                if field == "non_field_errors":
                    non_field_errors = errors
                    continue
                for message in errors:
                    field_errors.append({"field": field, "message": message})

        # Fallback status code
        status_code = 500
        if isinstance(exc, Http404):
            status_code = 404
        elif isinstance(exc, APIException):
            status_code = exc.status_code

        response.data = {
            "status_code": status_code,
            "type": data.get("type"),
            "detail": {
                "field_errors": field_errors,
                "non_field_errors": non_field_errors,
            },
            "fallback_message": data.get("fallback_message"),
        }

    return response


def get_formatted_exception(exc):
    """
    Get an exception formatted as a response body.
    """
    response = exception_handler(exc, {})
    if response and response.data:
        return response.data
    return None
