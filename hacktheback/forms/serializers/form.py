from rest_framework import serializers

from hacktheback.forms.models import Form, Question, QuestionOption


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        exclude = ("question",)


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = (
            "id",
            "order",
            "label",
            "type",
            "description",
            "placeholder",
            "required",
            "default_answer",
            "options",
        )

    def to_representation(self, instance):
        """
        Set `options` to return a null value if the type of the instance is not
        an option type.
        """
        ret = super().to_representation(instance)
        if instance.type not in Question.OPTION_TYPES:
            ret["options"] = None
        return ret


class FormSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, required=True)

    class Meta:
        model = Form
        fields = (
            "id",
            "title",
            "description",
            "type",
            "is_draft",
            "questions",
            "start_at",
            "end_at",
            "created_at",
        )


__all__ = ["FormSerializer"]
