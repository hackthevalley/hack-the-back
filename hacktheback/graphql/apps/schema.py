import graphene

from .resolvers import resolve_forms
from .types import Form


class AppsQueries(graphene.ObjectType):
    """
    All the queries within the "Apps" Django application.
    Of course, the resolver.py and types.py is linked with fake data that does
    not grab data from apps yet.
    """

    # Try going to http://127.0.0.1:8000/api/v1/graphql

    # Then run this query:
    # query Forms {
    #     forms {
    #         id
    #         title
    #         description
    #     }
    # }

    forms = graphene.List(Form, description="List of forms.")

    def resolve_forms(self, info):
        return resolve_forms(info)
