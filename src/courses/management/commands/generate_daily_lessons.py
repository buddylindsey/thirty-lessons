from django.core.management.base import BaseCommand

from courses.models import Course
from courses.services import GenerationError, generate_next_lesson


class Command(BaseCommand):
    help = "Generate one missing lesson for each active course."

    def add_arguments(self, parser):
        parser.add_argument("--no-email", action="store_true", help="Generate lessons without sending email.")

    def handle(self, *args, **options):
        generated = 0
        for course in Course.objects.filter(status=Course.Status.ACTIVE).order_by("id"):
            try:
                lesson = generate_next_lesson(course, send_email=not options["no_email"])
            except GenerationError as exc:
                self.stderr.write(f"Course {course.id}: {exc}")
                continue
            if lesson:
                generated += 1
                self.stdout.write(f"Generated lesson {lesson.id} for course {course.id} day {lesson.day_number}")
        self.stdout.write(f"Generated {generated} lessons.")
