from django.core import mail
from django.test import TestCase, override_settings

from courses.ai import AIProvider, set_ai_provider
from courses.models import Course, CourseMemory, Lesson, LessonFeedback
from courses.services import (
    GenerationError,
    build_daily_lesson_context,
    generate_next_lesson,
    generate_outline,
    send_lesson_email,
    start_course_conversation,
    update_memory,
)
from courses.tests.factories import course, lesson


class RecordingAI(AIProvider):
    def __init__(self):
        self.contexts = []

    def generate_initial_course_message(self, context):
        self.contexts.append(context)
        return "What should this course focus on?"

    def generate_chat_response(self, messages):
        return "assistant"

    def generate_course_outline(self, context):
        return [{"day": day, "title": f"Day {day}", "objective": f"Objective {day}"} for day in range(1, 31)]

    def generate_daily_lesson(self, context):
        self.contexts.append(context)
        return {"title": "Generated", "content_markdown": "# Generated", "summary": "Summary"}

    def update_course_memory(self, context):
        self.contexts.append(context)
        return "Remember more examples."


class FailingEmailBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise RuntimeError("smtp unavailable")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ServiceTests(TestCase):
    def tearDown(self):
        from courses.ai import FakeAIProvider

        set_ai_provider(FakeAIProvider())

    def test_daily_context_includes_bounded_history_feedback_and_memory(self):
        item = course(status=Course.ACTIVE)
        old = lesson(item, 1)
        lesson(item, 2)
        lesson(item, 3)
        lesson(item, 4)
        LessonFeedback.objects.create(lesson=old, feedback_type=LessonFeedback.MORE_EXAMPLES)
        CourseMemory.objects.create(course=item, content="Prefers examples.")

        context = build_daily_lesson_context(item, 5)

        self.assertEqual(context["course"]["stable_context"], "Stable context")
        self.assertEqual(context["outline_item"]["day"], 5)
        self.assertEqual(len(context["recent_lessons"]), 3)
        self.assertEqual(context["recent_feedback"][0]["feedback_type"], LessonFeedback.MORE_EXAMPLES)
        self.assertEqual(context["course_memory"], "Prefers examples.")

    def test_generate_next_lesson_creates_one_lesson_and_sends_email(self):
        item = course(status=Course.ACTIVE)

        generated = generate_next_lesson(item)

        self.assertEqual(generated.day_number, 1)
        self.assertEqual(Lesson.objects.filter(course=item).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("View lesson", mail.outbox[0].body)
        self.assertIn("/lessons/", mail.outbox[0].body)
        self.assertIn("?feedback=more_practical#feedback-modal", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        self.assertIn('<a href="http://localhost:8000/lessons/', mail.outbox[0].alternatives[0][0])
        self.assertIn("More practical</a>", mail.outbox[0].alternatives[0][0])
        generated.refresh_from_db()
        self.assertIsNotNone(generated.email_sent_at)

    def test_generate_outline_rejects_malformed_outline(self):
        provider = RecordingAI()
        provider.generate_course_outline = lambda context: [{"day": 1, "title": "", "objective": "Objective"}]
        set_ai_provider(provider)
        item = course()

        with self.assertRaises(GenerationError):
            generate_outline(item)

    def test_generate_next_lesson_rejects_malformed_lesson(self):
        provider = RecordingAI()
        provider.generate_daily_lesson = lambda context: {"title": "", "content_markdown": "# Generated", "summary": "Summary"}
        set_ai_provider(provider)
        item = course(status=Course.ACTIVE)

        with self.assertRaises(GenerationError):
            generate_next_lesson(item, send_email=False)

    def test_generate_next_lesson_does_not_duplicate_same_day(self):
        item = course(status=Course.ACTIVE)

        generate_next_lesson(item, send_email=False)
        generate_next_lesson(item, send_email=False)

        self.assertEqual(list(item.lessons.values_list("day_number", flat=True)), [1])

    def test_daily_generation_skips_non_active_courses(self):
        for status in [Course.DRAFT, Course.PAUSED, Course.COMPLETED, Course.ARCHIVED]:
            item = course(status=status)
            self.assertIsNone(generate_next_lesson(item, send_email=False))
            self.assertFalse(item.lessons.exists())

    def test_failed_email_keeps_generated_lesson_retryable(self):
        item = course(status=Course.ACTIVE)

        with override_settings(EMAIL_BACKEND="courses.tests.test_services.FailingEmailBackend"):
            generated = generate_next_lesson(item)

        self.assertIsNotNone(generated.id)
        generated.refresh_from_db()
        self.assertIsNone(generated.email_sent_at)

    def test_send_unsent_lesson_sets_email_sent_at(self):
        item = course(status=Course.ACTIVE)
        generated = lesson(item, 1)

        send_lesson_email(generated)

        generated.refresh_from_db()
        self.assertIsNotNone(generated.email_sent_at)
        self.assertIn("More practical", mail.outbox[0].body)
        self.assertIn("<h1>Lesson</h1>", mail.outbox[0].alternatives[0][0])
        self.assertNotIn("<script>", mail.outbox[0].alternatives[0][0])

    def test_lesson_email_does_not_duplicate_day_prefix_or_leading_heading(self):
        item = course(status=Course.ACTIVE)
        generated = Lesson.objects.create(
            course=item,
            day_number=1,
            title="Day 1: What a Piano Is, in Plain Language",
            content_markdown="# Day 1: What a Piano Is, in Plain Language\n\nUseful content.",
            summary="Summary",
        )

        send_lesson_email(generated)

        self.assertEqual(mail.outbox[0].subject, "Day 1: What a Piano Is, in Plain Language")
        self.assertEqual(mail.outbox[0].body.count("Day 1: What a Piano Is, in Plain Language"), 1)
        self.assertEqual(
            mail.outbox[0].alternatives[0][0].count("Day 1: What a Piano Is, in Plain Language"),
            1,
        )
        self.assertNotIn("<!doctype html>", mail.outbox[0].alternatives[0][0])

    def test_update_memory_uses_provider_abstraction(self):
        provider = RecordingAI()
        set_ai_provider(provider)
        item = course(status=Course.ACTIVE)
        generated = lesson(item, 1)
        LessonFeedback.objects.create(lesson=generated, feedback_type=LessonFeedback.CONFUSING)

        memory = update_memory(item)

        self.assertEqual(memory.content, "Remember more examples.")
        self.assertEqual(provider.contexts[0]["feedback"][0]["feedback_type"], LessonFeedback.CONFUSING)

    def test_start_course_conversation_creates_initial_assistant_message(self):
        provider = RecordingAI()
        set_ai_provider(provider)
        item = course()

        message = start_course_conversation(item)

        self.assertEqual(message.role, "assistant")
        self.assertEqual(message.content, "What should this course focus on?")
        self.assertEqual(provider.contexts[0]["course"]["title"], item.title)
