# Generated by Django 3.2.3 on 2021-05-16 23:05

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("hackathon", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Answer",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("answer", models.TextField(null=True)),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Form",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("title", models.CharField(max_length=128)),
                ("description", models.TextField()),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("HA", "Hacker Applicant"),
                            ("MI", "Miscellaneous"),
                        ],
                        default="MI",
                        max_length=2,
                    ),
                ),
                ("is_draft", models.BooleanField(default=True)),
                (
                    "hackathon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forms",
                        to="hackathon.hackathon",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        db_index=True, editable=False, verbose_name="order"
                    ),
                ),
                ("label", models.CharField(max_length=128)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("ST", "Short Text"),
                            ("LT", "Long Text"),
                            ("SL", "Select"),
                            ("MS", "Multiselect"),
                            ("HL", "Hyperlink"),
                            ("PH", "Phone"),
                            ("EM", "Email"),
                            ("RD", "Radio"),
                            ("FL", "File"),
                        ],
                        default="ST",
                        max_length=2,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        help_text="A question's help text.", null=True
                    ),
                ),
                (
                    "placeholder",
                    models.CharField(
                        help_text="The value for a question's HTML placeholder.",
                        max_length=128,
                        null=True,
                    ),
                ),
                ("required", models.BooleanField(default=False)),
                ("default_answer", models.TextField(null=True)),
                (
                    "form",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="forms.form",
                    ),
                ),
            ],
            options={
                "ordering": ("order",),
                "abstract": False,
                "unique_together": {("form", "label")},
            },
        ),
        migrations.CreateModel(
            name="Response",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_draft", models.BooleanField(default=True)),
                (
                    "form",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="forms.form",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="form_responses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="QuestionOption",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        db_index=True, editable=False, verbose_name="order"
                    ),
                ),
                ("label", models.CharField(max_length=128)),
                ("default_answer", models.BooleanField(default=False)),
                (
                    "persist_deletion",
                    models.BooleanField(
                        default=False,
                        help_text="The option has been deleted and won't be valid for future responses.",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="options",
                        to="forms.question",
                    ),
                ),
            ],
            options={
                "ordering": ("order",),
                "abstract": False,
                "unique_together": {("question", "label")},
            },
        ),
        migrations.CreateModel(
            name="AnswerOption",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "answer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="selected_options",
                        to="forms.answer",
                    ),
                ),
                (
                    "option",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="forms.questionoption",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="answer",
            name="question",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="answers",
                to="forms.question",
            ),
        ),
        migrations.AddField(
            model_name="answer",
            name="response",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="responses",
                to="forms.response",
            ),
        ),
    ]
