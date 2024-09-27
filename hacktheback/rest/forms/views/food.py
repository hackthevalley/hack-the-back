from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action

from hacktheback.forms.models import Food, HackerFoodTracking
from hacktheback.rest.forms.serializers import (FoodSerializer,
                                                FoodTrackingSerializer)
from hacktheback.rest.permissions import AdminSiteModelPermissions


class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Food.objects.all()
    # permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FoodSerializer

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        current_meal = Food.objects.filter(serving=True).values_list('id', flat=True)

        resp = {
            "all_food": serializer.data,
            "current_meal": current_meal
        }
        return Response(data=resp)

    @action(detail=False, methods=['get'], url_path='filter')
    def filter_foodId(self, request, *args, **kwargs):
        try:
            serving_day = request.query_params.get("day")
            serving_meal = request.query_params.get("meal")
            food_id = Food.objects.filter(name=serving_meal, day=serving_day).values_list('id', flat=True)
            return Response(data={"food_id": food_id}, status=status.HTTP_200_OK)
        except Food.DoesNotExist:
            return Response(data={"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)

    def partial_update(self, request, *args, **kwargs):
        # Get the food object
        instance = self.get_object()
        
        # Setting the current food to be served
        try:
            # food_serving_update = Food.objects.filter(id=request.query_params.get("food_id"))
            food_serving_update = Food.objects.filter(id=instance.id)
            if not food_serving_update.exists():
                return Response(data={"error": "Update not successfull"}, status=status.HTTP_404_NOT_FOUND)

            # Update table to have no serving food by setting all to False
            Food.objects.filter(serving=True).update(serving=False)

            food_serving_update.update(serving=True)
            return Response(data={"message": "Food serving updated successfully."}, status=status.HTTP_200_OK)

        except Food.DoesNotExist:
            return Response(data={"error": "Update not successfull"}, status=status.HTTP_404_NOT_FOUND)


class FoodTrackingViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = HackerFoodTracking.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FoodTrackingSerializer

    def create(self, request, *args, **kwargs):
        food = request.data.get("food")
        serializer = self.get_serializer(data=food, many=True)
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(data=serializer.data)
