import graphene

from .account.schema import AccountMutations
from .apps.schema import AppsQueries


class Query(AppsQueries):
    pass


class Mutation(AccountMutations):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
