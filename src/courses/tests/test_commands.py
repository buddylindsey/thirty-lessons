from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from courses.models import Course, CourseMemory, Lesson
from courses.tests.factories import course, lesson


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CommandTests(TestCase):
    def test_generate_daily_lessons_command_generates_for_active_only(self):
        active = course(status=Course.ACTIVE)
        paused = course(status=Course.PAUSED)
        output = StringIO()

        call_command("generate_daily_lessons", stdout=output)

        self.assertEqual(active.lessons.count(), 1)
        self.assertEqual(paused.lessons.count(), 0)
        self.assertIn("Generated 1 lessons", output.getvalue())

    def test_generate_daily_lessons_command_is_idempotent_same_day(self):
        active = course(status=Course.ACTIVE)

        call_command("generate_daily_lessons", no_email=True)
        call_command("generate_daily_lessons", no_email=True)

        self.assertEqual(list(active.lessons.values_list("day_number", flat=True)), [1])

    def test_send_unsent_lessons_retries_only_unsent(self):
        item = course(status=Course.ACTIVE)
        unsent = lesson(item, 1)
        sent = lesson(item, 2)
        sent.email_sent_at = sent.generated_at
        sent.save(update_fields=["email_sent_at"])

        call_command("send_unsent_lessons")

        unsent.refresh_from_db()
        sent.refresh_from_db()
        self.assertIsNotNone(unsent.email_sent_at)
        self.assertEqual(Lesson.objects.filter(email_sent_at__isnull=False).count(), 2)

    def test_update_course_memory_command_creates_memory(self):
        item = course(status=Course.ACTIVE)

        call_command("update_course_memory", item.id)

        self.assertTrue(CourseMemory.objects.filter(course=item).exists())
