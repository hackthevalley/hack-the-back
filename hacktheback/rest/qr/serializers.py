import re

from rest_framework import serializers

from hacktheback.forms.models import FormResponse
from hacktheback.rest.forms.serializers.food import FoodTrackingSerializer
from hacktheback.rest.forms.serializers.form_response import \
    HackathonApplicantSerializer


class QrAdminSerializer(serializers.ModelSerializer):
    application = serializers.UUIDField(read_only=True, source="id")
    applicant = HackathonApplicantSerializer()
    answers = serializers.SerializerMethodField()
    food = FoodTrackingSerializer(read_only=True, many=True)

    class Meta:
        model = FormResponse
        fields = (
            "id",
            "application",
            "user",
            "applicant",
            "answers",
            "food",
        )


    def to_camel_case(self, text):
        # remove non-alphanumeric characters

        s = text.replace("-", " ").replace("_", " ").replace("-", " ")
        s = [re.sub(r'\W+', '', word) for word in s.split()]
        if len(text) == 0:
            return text
        return s[0].lower() + ''.join(i.capitalize() for i in s[1:])

    def get_answers(self, instance):
        rep = {}
        for answer in instance.answers.all():
            text = answer.answer
            if not answer.answer:
                text = answer.answer_options.first().option.label
            rep[self.to_camel_case(answer.question.label)] = text

        return rep

