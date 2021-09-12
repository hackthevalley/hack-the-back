from typing import Any

from hacktheback.forms.models import Answer, FormResponse, Question
from hacktheback.rest.forms.serializers import AnswerSerializer


def answer_question_in_form_response(
    form_response: FormResponse, answer_data: Any
):
    """
    Provided answer data, create or update the answer in the database for
    the specified form response object. Returns a ReturnDict object.
    """
    # Validate request data
    serializer = AnswerSerializer(
        data=answer_data, context={"form_response": form_response}
    )
    serializer.is_valid(raise_exception=True)
    try:
        # Get answer to question if it exists
        question: Question = serializer.validated_data.get("question")
        answer = Answer.objects.get(question=question, response=form_response)
        serializer.instance = answer
    except Answer.DoesNotExist:
        pass
    # Create or update the answer
    serializer.save()
    return serializer.data
