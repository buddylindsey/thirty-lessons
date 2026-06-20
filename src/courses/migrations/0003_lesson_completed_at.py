from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0002_lessondiscussionmessage"),
    ]

    operations = [
        migrations.AddField(
            model_name="lesson",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
