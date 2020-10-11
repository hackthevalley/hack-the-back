import graphene

from .apps.schema import AppsQueries


class Query(AppsQueries):
    pass


class Mutation(graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query)
