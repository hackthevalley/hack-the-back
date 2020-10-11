from graphene_django import views


class GraphQLView(views.GraphQLView):
    # TODO: This can be done better as GraphQLView is expecting to load
    # Graphiql instead of GraphQL Playground
    graphiql_template = "graphql/playground.html"
