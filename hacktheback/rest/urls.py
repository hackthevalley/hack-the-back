from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularJSONAPIView,
    SpectacularSwaggerView,
    SpectacularYAMLAPIView,
)

# noinspection PyUnresolvedReferences
from hacktheback.rest.openapi import JSONWebTokenAuthenticationScheme

# URL patterns for hacker APIs
hacker_urlpatterns = [
    path("", include("hacktheback.rest.forms.hacker_urls")),
]

# URL patterns for admin APIs
admin_urlpatterns = [
    path("account/", include("hacktheback.rest.account.admin_urls")),
    path("", include("hacktheback.rest.forms.admin_urls")),
]

urlpatterns = [
    path("account/", include("hacktheback.rest.account.urls")),
    path("", include(hacker_urlpatterns)),
    path("admin/", include(admin_urlpatterns)),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("schema.json", SpectacularJSONAPIView.as_view(), name="schema-json"),
    path("schema.yaml", SpectacularYAMLAPIView.as_view(), name="schema-yaml"),
    path(
        "swagger",
        SpectacularSwaggerView.as_view(url_name="schema-yaml"),
        name="swagger",
    ),
]
