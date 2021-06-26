import graphene

from hacktheback.graphql.account.schema import AccountMutations, AccountQueries


class Query(AccountQueries):
    pass


class Mutation(AccountMutations):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
