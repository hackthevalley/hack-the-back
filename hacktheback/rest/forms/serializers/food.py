from rest_framework import serializers

from hacktheback.forms.models import Food, HackerFoodTracking


class FoodSerializer(serializers.ModelSerializer):

    class Meta:
        model = Food
        fields = (
            "id",
            "name",
            "day",
            "end_time", # TODO: Change to have a boolean that can be toggled
        )

class FoodTrackingSerializer(serializers.ModelSerializer):

    class Meta:
        model = HackerFoodTracking
        fields = (
            "application",
            "serving",
        )
