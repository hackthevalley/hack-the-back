from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hacktheback.forms.models import Food, HackerFoodTracking
from hacktheback.rest.forms.serializers import (FoodSerializer,
                                                FoodTrackingSerializer)
from hacktheback.rest.permissions import AdminSiteModelPermissions


class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Food.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FoodSerializer

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        current_time = timezone.now()
        current_meal = None
        for food in Food.objects.all().order_by("end_time"):
            if food.end_time >= current_time:
                current_meal = food.id
                break

        resp = {
            "all_food": serializer.data,
            "current_meal": current_meal
        }
        return Response(data=resp)


class FoodTrackingViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = HackerFoodTracking.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FoodTrackingSerializer

    def create(self, request, *args, **kwargs):
        food = request.data.getlist("food")
        serializer = self.get_serializer(data=food, many=True)
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(data=serializer.data)#
