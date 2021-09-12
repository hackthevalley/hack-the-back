from django.db import transaction
from rest_framework import serializers

from hacktheback.forms.models import Form, Question, QuestionOption


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        exclude = ("question",)

    def create(self, validated_data):
        """
        Create a new :model: `forms.QuestionOption` object.
        """
        question = self.context["question"]
        return QuestionOption.objects.create(
            question=question, **validated_data
        )


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(
        many=True, required=False, read_only=True
    )

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

    def create(self, validated_data):
        """
        Create a new :model: `forms.Question` object.
        """
        form = self.context["form"]
        return Question.objects.create(form=form, **validated_data)

    def update(self, instance, validated_data):
        """
        Update a :model: `forms.Question` object.
        """
        with transaction.atomic():
            # Save Question object
            instance.label = validated_data.get("label", instance.label)
            prev_type = instance.type
            instance.type = validated_data.get("type", instance.type)
            instance.description = validated_data.get(
                "description", instance.description
            )
            instance.placeholder = validated_data.get(
                "placeholder", instance.placeholder
            )
            instance.required = validated_data.get(
                "required", instance.required
            )
            instance.default_answer = validated_data.get(
                "default_answer", instance.default_answer
            )
            instance.save()

            if (
                instance.type in Question.NON_OPTION_TYPES
                and prev_type in Question.OPTION_TYPES
            ):
                # Delete previous options if the question was an option
                # type but no longer is that type anymore
                QuestionOption.objects.filter(question=instance).delete()
        return


class FormSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

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
