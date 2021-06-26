import graphene


class FieldErrorField(graphene.ObjectType):
    field = graphene.String(
        required=True, description="Input field which has an error."
    )
    message = graphene.String(
        required=True,
        description="The error for the input field it was grouped with.",
    )


class DetailField(graphene.ObjectType):
    field_errors = graphene.List(
        graphene.NonNull(FieldErrorField),
        required=True,
        description="Errors related to specific input fields.",
    )
    non_field_errors = graphene.List(
        graphene.NonNull(graphene.String),
        required=True,
        description="Errors not related to specific input fields.",
    )


class Errors(graphene.ObjectType):
    """
    Errors for this mutation. Should be `null` if operation was successful.
    """

    status_code = graphene.Int(
        required=True,
        description="The status code if this was a REST operation.",
    )
    type = graphene.String(required=True, description="The error type raised.")
    detail = graphene.Field(
        DetailField,
        required=True,
        description="Specific details about the error.",
    )
    fallback_message = graphene.String(
        required=True,
        description="The fallback message if `detail` isn't used. Note that "
        "this doesn't provide all the errors.",
    )
