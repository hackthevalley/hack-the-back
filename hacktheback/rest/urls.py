from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularJSONAPIView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)

urlpatterns = [
    path("account/", include("hacktheback.rest.account.urls")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("schema.json", SpectacularJSONAPIView.as_view(), name="schema-json"),
    path("schema.yaml", SpectacularYAMLAPIView.as_view(), name="schema-yaml"),
    path(
        "swagger",
        SpectacularSwaggerView.as_view(url_name="schema-yaml"),
        name="swagger",
    ),
]
