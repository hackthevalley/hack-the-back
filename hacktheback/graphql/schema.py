import graphene

from hacktheback.graphql.account.schema import AccountMutations
from hacktheback.graphql.apps.schema import AppsQueries


class Query(AppsQueries):
    pass


class Mutation(AccountMutations):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
