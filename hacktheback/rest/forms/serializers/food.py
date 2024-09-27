from rest_framework import serializers

from hacktheback.forms.models import Food, HackerFoodTracking


class FoodSerializer(serializers.ModelSerializer):

    class Meta:
        model = Food
        fields = (
            "id",
            "name",
            "day",
            "serving",
        )

    def validate(self, data):
        serving_day = data.get('day')
        serving_meal = data.get('meal_name')

        if not day or not meal_name:
            raise serializers.ValidationError("The start date must be earlier than the end date.")

        return data

class FoodTrackingSerializer(serializers.ModelSerializer):

    class Meta:
        model = HackerFoodTracking
        fields = (
            "application",
            "serving",
        )
