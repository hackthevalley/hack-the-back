from typing import List

import phonenumbers
import qrcode

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
    pn = phonenumbers.parse(number, "US")
    return phonenumbers.format_number(
        pn, phonenumbers.PhoneNumberFormat.E164
    )


def format_email_address(email: str) -> str:
    """
    Returns a formatted email address.
    """
    return email.lower()


def format_short_text(text: str) -> str:
    """
    If the text is an integer, then remove the leading zeros, otherwise do nothing
    """
    if text.isdigit():
        return str(int(text))
    return text


def format_answer(answer: str, ftype: str):
    """
    Format and return answer based on type.
    """
    if ftype == Question.QuestionType.PHONE:
        return format_phone_number(answer)
    elif ftype == Question.QuestionType.EMAIL:
        return format_email_address(answer)
    elif ftype == Question.QuestionType.SHORT_TEXT:
        return format_short_text(answer)
    return answer

def send_rsvp_email(uuid: str, email: str):
    print(uuid)
    print(email)
    qr = qrcode.make(uuid)
    qr.save("qrcodes/qr.png")
