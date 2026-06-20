from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0003_lesson_completed_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lessonfeedback",
            name="feedback_type",
            field=models.CharField(
                choices=[
                    ("too_easy", "Too easy"),
                    ("too_hard", "Too hard"),
                    ("good_pacing", "Good pacing"),
                    ("more_practical", "More practical"),
                    ("more_theory", "More theory"),
                    ("more_examples", "More examples"),
                    ("confusing", "Confusing"),
                    ("skip_ahead", "Skip ahead"),
                    ("custom_comment", "Comment"),
                    ("completion_note", "Completion note"),
                ],
                max_length=40,
            ),
        ),
    ]
