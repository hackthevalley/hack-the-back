from django.conf import settings
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from graphql_jwt.decorators import jwt_cookie

from hacktheback.graphql.schema import schema
from hacktheback.graphql.views import GraphQLView

urlpatterns = [
    path(
        "api/graphql",
        csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema)),
    ),
]

if settings.JWT_AUTH["JWT_COOKIE"]:
    urlpatterns = [
        path(
            "api/graphql",
            jwt_cookie(GraphQLView.as_view(graphiql=True, schema=schema)),
        ),
    ]

urlpatterns += [
    path("api/", include("hacktheback.rest.urls")),
]
