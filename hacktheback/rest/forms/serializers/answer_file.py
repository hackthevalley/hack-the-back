import filetype
from django.utils.translation import gettext as _
from rest_framework import serializers

from hacktheback.core.serializers import ValidationMixin
from hacktheback.forms.models import AnswerFile, Form, Question
from hacktheback.validators import validate_file_size


class AnswerFileSerializer(serializers.ModelSerializer, ValidationMixin):

    file = serializers.FileField(
        write_only=True, validators=[validate_file_size]
    )

    field_error_messages = {
        "invalid_pdf_file": (
            "file",
            _("The file must be a PDF."),
        ),
        "invalid_image_file": (
            "file",
            _(
                "The file must be an image. Supported file types include "
                "JPG and PNG."
            ),
        ),
        "invalid_file": ("file", _("This file is not acceptable.")),
        "invalid_question": (
            "question",
            _("The question does not require a file to be uploaded."),
        ),
    }

    class Meta:
        model = AnswerFile
        fields = "__all__"
        read_only_fields = ("user", "original_filename")

    def create(self, validated_data):
        """
        Create a new file. Store the original file name and the user who
        uploaded it.
        """
        file = validated_data.get("file")
        user = self.context["request"].user
        return AnswerFile.objects.create(
            user=user, original_filename=file.name, **validated_data
        )

    def validate(self, data):
        """
        Validate that the question requires a file to be uploaded. Also check
        that the file has an acceptable MIME type based on the question asked.
        """
        file = data.get("file")
        question = data.get("question")

        if question.type not in Question.FILE_TYPES:
            self.fail_for_field("invalid_question")

        kind = filetype.guess(file.read())
        if kind is None:
            if question.type == Question.QuestionType.IMAGE_FILE:
                self.fail_for_field("invalid_image_file")
            elif question.type == Question.QuestionType.PDF_FILE:
                self.fail_for_field("invalid_pdf_file")
            else:
                self.fail_for_field("invalid_file")
        if (
            question.type == Question.QuestionType.IMAGE_FILE
            and kind.mime not in ["image/jpeg", "image/png"]
        ):
            self.fail_for_field("invalid_image_file")
        elif (
            question.type == Question.QuestionType.PDF_FILE
            and kind.mime not in ["application/pdf"]
        ):
            self.fail_for_field("invalid_pdf_file")

        return data


class HackerApplicationAnswerFileSerializer(AnswerFileSerializer):
    default_error_messages = {
        "question_not_in_ha_form": _(
            "The question is not in the Hacker Application form."
        )
    }

    def validate(self, data):
        """
        Validate that the question is in the hacker application form. Then,
        continue running validations to check that the question requires a file
        to be uploaded and that the file has an acceptable MIME type based on
        the question asked.
        """
        question = data.get("question")
        if question.form.type != Form.FormType.HACKER_APPLICATION:
            self.fail("question_not_in_ha_form")
        return super().validate(data)
