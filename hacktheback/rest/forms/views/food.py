from datetime import datetime

from django.conf import settings
from drf_spectacular.utils import extend_schema
from graphql_jwt.utils import set_cookie
from rest_framework import generics, status, viewsets
from rest_framework.response import Response

from hacktheback.forms.models import Food, HackerFoodTracking
from hacktheback.rest.forms.serializers import FoodSerializer, FoodTrackingSerializer

from hacktheback.rest.account.serializers import (
    JSONWebTokenBasicAuthSerializer,
    JSONWebTokenSocialAuthSerializer,
    RefreshJSONWebTokenSerializer,
    VerifyJSONWebTokenSerializer,
)

class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Food.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FoodSerializer


class FoodTrackingViewSet(viewsets.ModelViewSet):
    queryset = HackerFoodTracking.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FoodTrackingSerializer
