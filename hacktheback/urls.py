from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt

from .graphql.schema import schema
from .graphql.views import GraphQLView

urlpatterns = [
    path(
        "api/v1/graphql",
        csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema)),
    ),
    path("social/", include("social_django.urls", namespace="social")),
]
