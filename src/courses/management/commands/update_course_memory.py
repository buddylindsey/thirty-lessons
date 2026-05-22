from django.core.management.base import BaseCommand

from courses.models import Course
from courses.services import update_memory


class Command(BaseCommand):
    help = "Update compressed course memory for courses with lessons or feedback."

    def add_arguments(self, parser):
        parser.add_argument("course_id", nargs="?", type=int)

    def handle(self, *args, **options):
        courses = Course.objects.all().order_by("id")
        if options["course_id"]:
            courses = courses.filter(id=options["course_id"])
        updated = 0
        for course in courses:
            memory = update_memory(course)
            updated += 1
            self.stdout.write(f"Updated memory {memory.id} for course {course.id}")
        self.stdout.write(f"Updated {updated} course memories.")
