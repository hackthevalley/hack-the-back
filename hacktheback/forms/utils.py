from typing import List

import phonenumbers

from hacktheback.forms.models import Form, Question


def get_missing_questions(required: List[Question], answered: List[Question]):
    """
    Returns a list of missing questions, provided that a list of required
    questions and list of answered questions are provided.
    """
    missing_questions: List[Question] = []
    for required_question in required:
        required_question_answered = False
        for answered_question in answered:
            if required_question == answered_question:
                required_question_answered = True
                break
        if not required_question_answered:
            missing_questions.append(required_question)
    return missing_questions


def format_phone_number(number: str) -> str:
    """
    Returns a formatted phone number.
    """
    pn = phonenumbers.parse(number)
    return phonenumbers.format_number(
        pn, phonenumbers.PhoneNumberFormat.E164
    )


def format_email_address(email: str) -> str:
    """
    Returns a formatted email address.
    """
    return email.lower()


def format_answer(answer: str, ftype: str):
    """
    Format and return answer based on type.
    """
    if ftype == Question.QuestionType.PHONE:
        return format_phone_number(answer)
    elif ftype == Question.QuestionType.EMAIL:
        return format_email_address(answer)
    return answer
