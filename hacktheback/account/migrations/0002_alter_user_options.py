# Generated by Django 3.2.7 on 2021-09-23 00:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={"ordering": ["first_name"]},
        ),
    ]