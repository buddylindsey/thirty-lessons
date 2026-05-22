from django.core.management.base import BaseCommand

from courses.models import Lesson
from courses.services import send_lesson_email


class Command(BaseCommand):
    help = "Retry email delivery for lessons that have not been sent."

    def handle(self, *args, **options):
        sent = 0
        for lesson in Lesson.objects.filter(email_sent_at__isnull=True).order_by("course_id", "day_number"):
            try:
                send_lesson_email(lesson)
            except Exception as exc:
                self.stderr.write(f"Lesson {lesson.id}: {exc}")
                continue
            sent += 1
            self.stdout.write(f"Sent lesson {lesson.id}")
        self.stdout.write(f"Sent {sent} lessons.")
