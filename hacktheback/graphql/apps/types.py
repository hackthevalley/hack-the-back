import graphene


class Form(graphene.ObjectType):
    """
    An example of a Form object type (not linked to model).
    """

    title = graphene.String(description="This is a title.")
    description = graphene.String(description="This is a description.")

    class Meta:
        interfaces = [graphene.relay.Node]
