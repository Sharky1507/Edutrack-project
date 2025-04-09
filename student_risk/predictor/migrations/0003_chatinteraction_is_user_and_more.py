# Generated by Django 5.1.7 on 2025-04-09 09:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("predictor", "0002_studentassessment_bedtime_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatinteraction",
            name="is_user",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="chatinteraction",
            name="assessment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="predictor.studentassessment",
            ),
        ),
        migrations.AlterField(
            model_name="chatinteraction",
            name="response",
            field=models.TextField(blank=True, null=True),
        ),
    ]
