from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter


def id_or_type_parameter(name="id_or_type"):
    return OpenApiParameter(
        name,
        OpenApiTypes.STR,
        OpenApiParameter.PATH,
        required=True,
        description="A UUID or type string identifying the form.",
        examples=[
            OpenApiExample(
                "UUID", "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            ),
            OpenApiExample(
                "Hacker Application Type", "hacker_application"
            ),
        ]
    )
