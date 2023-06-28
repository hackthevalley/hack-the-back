from typing import Any, List, Optional

import phonenumbers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework import serializers

from hacktheback.core.serializers import ValidationMixin
from hacktheback.forms import utils
from hacktheback.forms.models import (Answer, AnswerFile, AnswerOption, Form,
                                      FormResponse, HackathonApplicant,
                                      Question, QuestionOption)
from hacktheback.rest.account.serializers import UserSerializer


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = (
            "id",
            "option",
        )


class AnswerSerializer(serializers.ModelSerializer, ValidationMixin):
    answer_options = AnswerOptionSerializer(
        many=True, required=False, allow_null=True
    )

    field_error_messages = {
        "answer_is_required": ("answer", _("An answer is required.")),
        "invalid_phone_number": (
            "answer",
            _("The answer provided is not a valid phone number."),
        ),
        "invalid_email": (
            "answer",
            _("The answer provided is not a valid email address."),
        ),
        "invalid_http_url": (
            "answer",
            _(
                "The answer provided is not a valid url with an HTTP or "
                "HTTPS scheme."
            ),
        ),
        "invalid_file": (
            "answer",
            _(
                "The answer provided is not a valid identifier for an "
                "uploaded file for the associated question."
            ),
        ),
        "only_answer_field": (
            "answer_options",
            _("Only the answer field can contain the answer."),
        ),
        "only_answer_options_field": (
            "answer",
            _("Only answer_options field can contain the answer."),
        ),
        "answer_options_for_same_option": (
            "answer_options",
            _(
                "There shouldn't be multiple answer options to the same "
                "option."
            ),
        ),
        "more_than_one_answer_option": (
            "answer_options",
            _(
                "There cannot be more than one selected option for this "
                "answer."
            ),
        ),
        "invalid_answer_option": (
            "answer_options",
            _("The selected option(s) are not valid choices."),
        ),
    }

    default_error_messages = {
        "answer_for_invalid_question": _(
            "The answer is not for a valid question in the form."
        )
    }

    class Meta:
        model = Answer
        fields = (
            "id",
            "question",
            "answer",
            "answer_options",
        )

    def _get_form_question_instances(self) -> Optional[List[Question]]:
        if self.root and hasattr(self.root, "form_question_instances"):
            return self.root.form_question_instances
        if self.context.get("form_response", None) is not None:
            form_response = self.context.get("form_response")
            if isinstance(form_response, FormResponse):
                return list(Question.objects.filter(form=form_response.form))
        raise Exception(
            "To use this serializer, please provide a FormResponse object in "
            "the context with `form_response` as the key."
        )

    def _run_validation_for_non_option_type(
        self, data: Any, question: Question
    ) -> None:
        """
        This validates multiple requirements for an answer that has a
        corresponding question that of a non-option type:
        - The `answer_options` field must be null
        - The 'answer` field must have at least one character if the
          corresponding question has `required` set to True
        - The `answer` field is in the correct format, depending on the
          type of question the answer corresponds to
        """
        # Check that `answer` field is filled if the question says its required
        # and also check that the `answer_options` field is null
        if data.get("answer_options") is not None:
            self.fail_for_field("only_answer_field")
        if question.required and (
            data.get("answer") is None or data.get("answer").strip() == ""
        ):
            self.fail_for_field("answer_is_required")

        # Validate if the `answer` field is in the correct format
        if question.type == Question.QuestionType.PHONE:
            try:
                pn = phonenumbers.parse(data.get("answer"))
                if not phonenumbers.is_valid_number(pn):
                    self.fail_for_field("invalid_phone_number")
            except phonenumbers.NumberParseException:
                self.fail_for_field("invalid_phone_number")
        elif question.type == Question.QuestionType.EMAIL:
            try:
                validate_email(data.get("answer"))
            except DjangoValidationError:
                self.fail_for_field("invalid_email")
        elif question.type == Question.QuestionType.HTTP_URL:
            try:
                validate_url = URLValidator(schemes=["http", "https"])
                validate_url(data.get("answer"))
            except DjangoValidationError:
                self.fail_for_field("invalid_http_url")
        elif question.type in [
            Question.QuestionType.PDF_FILE,
            Question.QuestionType.IMAGE_FILE,
        ]:
            try:
                af = AnswerFile.objects.get(id=data.get("answer"))
                if af.question.id != question.id:
                    self.fail_for_field("invalid_file")
            except AnswerFile.DoesNotExist:
                self.fail_for_field("invalid_file")

    def _run_validation_for_option_type(
        self, data: Any, question: Question
    ) -> None:
        """
        This validates multiple requirements for an answer that has a
        corresponding question that of an option type:
            - The `answer` field must be null and that the `answer_options`
              field is not null
            - The `answer_options` field must have at least one selected option
              if the corresponding question has `required` set to True
            - Each selected option in the `answer_options` field must only
              correspond to one option
            - The `answer_options` field must have at most one selected option
              if the option type is solo (i.e. radio or select)
            - The `answer_options` must contain valid answers for options
              for the corresponding question
        """
        # Validate that `answer` field is null and that the `answer_options`
        # field is not null
        if (
            data.get("answer") is not None
            or data.get("answer_options") is None
        ):
            self.fail_for_field("only_answer_options_field")

        # Validate that at least one option is selected if the question
        # says its required
        if question.required and len(data.get("answer_options")) == 0:
            self.fail_for_field("answer_is_required")

        # Validate that there aren't more than one answer options for the
        # same option and that each option is a valid option for the
        # question
        answered_options = set()
        for answer_option in data.get("answer_options"):
            option: QuestionOption = answer_option["option"]
            if option in answered_options:
                self.fail_for_field("answer_options_for_same_option")
            answered_options.add(option)
            if option.question != question:
                self.fail_for_field("invalid_answer_option")

        # Validate that there can only be one answer option for solo option
        # types
        if (
            question.type in Question.SOLO_OPTION_TYPES
            and len(data.get("answer_options")) > 1
        ):
            self.fail_for_field("more_than_one_answer_option")

    def validate(self, data: Any) -> Any:
        """
        This validates multiple requirements for an answer depending on the
        corresponding question's type. This also validates that the answer
        is for the valid question in the form.
        """
        question: Question = data.get("question")

        if question.type in Question.NON_OPTION_TYPES:
            self._run_validation_for_non_option_type(data, question)
        elif question.type in Question.OPTION_TYPES:
            self._run_validation_for_option_type(data, question)

        # Validate that the answer is for the right question
        form_questions = self._get_form_question_instances()
        if form_questions is not None and question not in form_questions:
            self.fail("answer_for_invalid_question")

        return data

    def create(self, data: Any) -> Answer:
        """
        Create a new :model: `forms.Answer` object and associated :model:
        `forms.AnswerOption` objects.
        """
        with transaction.atomic():
            answer_options = None
            if data.get("answer_options"):
                answer_options = data.pop("answer_options")
            # Format data in `answer` field before it's placed inside the
            # database.
            question: Question = data.get("question")
            form_response = self.context.get("form_response")
            data["answer"] = utils.format_answer(
                data.get("answer"), question.type
            )
            answer_obj = Answer.objects.create(response=form_response, **data)
            if answer_options:
                for answer_option in answer_options:
                    AnswerOption.objects.create(
                        answer=answer_obj, **answer_option
                    )
        return answer_obj

    def update(self, instance: Answer, validated_data: Any) -> Answer:
        """
        Update a :model: `forms.Answer` object and create associated :model:
        `forms.AnswerOption` objects. Delete past associated :model:
        `forms.AnswerOption` objects as well.
        """
        with transaction.atomic():
            question: Question = validated_data.get("question")
            answer_options = validated_data.get("answer_options", None)

            if question.type in Question.NON_OPTION_TYPES:
                instance.answer = utils.format_answer(validated_data.get("answer", instance.answer), instance.question.type)
                instance.save()
            else:
                # Delete all past answer options
                AnswerOption.objects.filter(answer=instance).delete()
                # Create new answer options
                for answer_option in answer_options:
                    AnswerOption.objects.create(
                        answer=instance, **answer_option
                    )
        return instance


class HackathonApplicantSerializer(serializers.ModelSerializer):
    class Meta:
        model = HackathonApplicant
        fields = ("status",)


class FormResponseSerializer(serializers.ModelSerializer, ValidationMixin):
    applicant = HackathonApplicantSerializer(read_only=True)
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = FormResponse
        fields = (
            "id",
            "form",
            "user",
            "is_draft",
            "answers",
            "created_at",
            "updated_at",
            "applicant",
        )
        read_only_fields = ("user",)


class HackerApplicationResponseSerializer(FormResponseSerializer):
    answers = AnswerSerializer(many=True, required=True)

    field_error_messages = {
        "answers_for_same_question": (
            "answers",
            _(
                "There should not be multiple answers to the same question "
                "`{question}`."
            ),
        ),
        "missing_questions": (
            "answers",
            _("Not all required questions have been answered: {questions}"),
        ),
        "invalid_question_in_form": {
            "answers",
            _("This is not a valid question in the form: {question}"),
        },
    }

    class Meta(FormResponseSerializer.Meta):
        pass

    def __init__(self, *args, **kwargs):
        self._form = None
        self._form_questions = None
        super().__init__(*args, **kwargs)

    @property
    def form_instance(self) -> Optional[Form]:
        """
        Returns the model: `forms.Form` associated with the response for
        this serializer.
        """
        if self._form is not None:
            return self._form
        if self.initial_data and self.initial_data.get("form"):
            try:
                self._form = Form.objects.get(id=self.initial_data.get("form"))
                return self._form
            except Form.DoesNotExist:
                pass
        return None

    @property
    def form_question_instances(
        self,
    ) -> Optional[List[Question]]:
        """
        Returns a list of :model: `forms.Question` for the form associated with
        the response for this serializer.
        """
        if self._form_questions is not None:
            return self._form_questions
        if self.initial_data and self.initial_data.get("form"):
            try:
                self._form_questions = list(
                    Question.objects.filter(
                        form__id=self.initial_data.get("form")
                    )
                )
                return self._form_questions
            except Form.DoesNotExist:
                pass
        return []

    def validate(self, data: Any):
        """
        Validate that:
        - there aren't any duplicate answers
        - if is_draft is False, that all answers to required questions
          are provided in the response
        """
        answers: List[Any] = data.get("answers")
        answered_questions = list()
        required_questions = list(
            Question.objects.filter(form=data.get("form"), required=True)
        )

        # Validate that there aren't any duplicate answers
        for answer in answers:
            question: Question = answer.get("question")
            if question in answered_questions:
                self.fail_for_field(
                    "answers_for_same_question", **{"question": question.label}
                )
            answered_questions.append(question)

        # If `is_draft` is set to False, validate that all answers to
        # required questions are provided in the response
        if not data.get("is_draft"):
            missing_questions: List[Question] = utils.get_missing_questions(
                required_questions, answered_questions
            )
            if len(missing_questions) > 0:
                self.fail_for_field(
                    "missing_questions",
                    **{
                        "questions": "; ".join(
                            str(q) for q in missing_questions
                        )
                    },
                )
        return data

    def create(self, validated_data: Any) -> FormResponse:
        """
        Create a new :model: `forms.FormResponse` object, associated :model:
        `forms.Answer` objects and associated :model: `forms.AnswerOption`
        objects.
        """
        answers = validated_data.pop("answers")
        user = self.context["request"].user
        with transaction.atomic():
            form_response_obj = FormResponse.objects.create(
                user=user, **validated_data
            )
            for answer in answers:
                answer_options = None
                if "answer_options" in answer.keys():
                    answer_options = answer.pop("answer_options")
                # Format data in `answer` field before it's placed inside the
                # database.
                question: Question = answer.get("question")
                answer["answer"] = utils.format_answer(
                    answer.get("answer"), question.type
                )
                answer_obj = Answer.objects.create(
                    response=form_response_obj, **answer
                )
                if answer_options:
                    for answer_option in answer_options:
                        AnswerOption.objects.create(
                            answer=answer_obj, **answer_option
                        )
            if form_response_obj.form.type == Form.FormType.HACKER_APPLICATION:
                if validated_data.get("is_draft"):
                    HackathonApplicant.objects.create(
                        application=form_response_obj,
                        status=HackathonApplicant.Status.APPLYING,
                    )
                else:
                    HackathonApplicant.objects.create(
                        application=form_response_obj,
                        status=HackathonApplicant.Status.APPLIED,
                    )
        return form_response_obj

    def update(
        self, instance: FormResponse, validated_data: Any
    ) -> FormResponse:
        """
        This serializer cannot handle updates.
        """
        raise Exception("This has not been implemented.")


class HackerApplicationResponseAdminSerializer(FormResponseSerializer):
    """
    This contains the `applicant` associated object which should only be shown
    to admin users.
    """

    user = UserSerializer(read_only=True)

    class Meta(FormResponseSerializer.Meta):
        fields = FormResponseSerializer.Meta.fields + (
            "admin_notes",
            "user",
        )
        read_only_fields = FormResponseSerializer.Meta.fields


class HackerApplicationBatchStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=HackathonApplicant.Status,
        required=True,
        help_text="The status to update to.",
    )
    responses = serializers.PrimaryKeyRelatedField(
        queryset=FormResponse.objects.all(),
        many=True,
        required=True,
        allow_null=False,
        allow_empty=False,
        help_text="The ids of the hacker application responses to update.",
    )


class HackerApplicationApplicantStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=HackathonApplicant.Status.choices)
    count = serializers.IntegerField()


class HackerApplicationOverviewSerializer(serializers.Serializer):
    overview = HackerApplicationApplicantStatusSerializer(many=True)


__all__ = [
    "HackerApplicationResponseSerializer",
    "HackerApplicationResponseAdminSerializer",
    "FormResponseSerializer",
    "HackerApplicationBatchStatusUpdateSerializer",
    "HackerApplicationOverviewSerializer",
    "AnswerSerializer",
]
