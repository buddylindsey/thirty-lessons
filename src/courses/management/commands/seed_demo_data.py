from django.core.management.base import BaseCommand

from courses.models import Course, Topic
from courses.services import generate_outline


class Command(BaseCommand):
    help = "Create a small demo topic and draft course."

    def handle(self, *args, **options):
        topic, _ = Topic.objects.get_or_create(
            title="Piano History",
            defaults={"description": "A sample topic for a 30-day learning program."},
        )
        course, created = Course.objects.get_or_create(
            topic=topic,
            title="Piano History 30-Day Program",
            defaults={
                "goal": "Understand composers and piano evolution.",
                "audience_level": "Beginner",
                "lesson_style": "Practical and historical",
                "daily_time_commitment": "20 minutes",
                "stable_context": "Beginner course focused on composers and piano evolution.",
            },
        )
        if created or not course.has_valid_outline():
            generate_outline(course)
        self.stdout.write(f"Demo course ready: {course.id}")
