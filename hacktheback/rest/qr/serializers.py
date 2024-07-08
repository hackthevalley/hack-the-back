from rest_framework import serializers
from hacktheback.forms.models import FormResponse, Answer, Question, AnswerOption, QuestionOption, HackerFoodTracking
from hacktheback.rest.forms.serializers.form_response import AnswerSerializer, HackathonApplicantSerializer, UserSerializer
from hacktheback.rest.forms.serializers.food import FoodTrackingSerializer

class QrAnswerAdminSerializer(AnswerSerializer):
    def to_representation(self, instance):
        data = super(QrAnswerAdminSerializer, self).to_representation(instance)
        data["question"] = Question.objects.get(pk=data.get("question")).label

        if data.get("answer_options") and len(data.get("answer_options")) > 0:
            _, option_id = data.get("answer_options")[0].values()
            data["answer"] = QuestionOption.objects.get(pk=option_id).label
        del data["answer_options"]
        return data

class QrAdminSerializer(serializers.ModelSerializer):
    applicant = HackathonApplicantSerializer(read_only=True)
    answers = QrAnswerAdminSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    food = FoodTrackingSerializer(read_only=True, many=True)

    class Meta:
        model = FormResponse
        fields = (
            "id",
            "user",
            "answers",
            "applicant",
            "food",
        )
