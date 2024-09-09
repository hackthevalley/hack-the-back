from rest_framework import serializers

from hacktheback.forms.models import Form

class FormControllerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Form
        fields = (
            "id",
            "created_at",
            "start_at",
            "end_at",
            "title",
            "description",
            "type",
            "is_draft",
        )
    
    def validate(self, data):
        start_at = data.get('start_at')
        end_at = data.get('end_at')

        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError("The start date must be earlier than the end date.")

        return data