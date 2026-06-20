from django.test import TestCase
from django.urls import reverse

from courses.models import ChatMessage, Course, Lesson, LessonDiscussionMessage, LessonFeedback, Topic
from courses.tests.factories import course, lesson


class ViewTests(TestCase):
    def test_topic_creation_rejects_empty_title(self):
        response = self.client.post(reverse("courses:topic_create"), {"title": "", "description": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertEqual(Topic.objects.count(), 0)

    def test_chat_persists_user_and_assistant_messages(self):
        item = course()

        response = self.client.post(
            reverse("courses:chat_submit", args=[item.id]),
            {"message": "Focus on composers."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatMessage.objects.filter(course=item).count(), 2)
        self.assertContains(response, "Focus on composers.")
        self.assertContains(response, "A useful next step")

    def test_course_creation_starts_refinement_chat(self):
        item = Topic.objects.create(title="Rust", description="Systems programming")

        response = self.client.post(
            reverse("courses:course_create", args=[item.id]),
            {
                "title": "Rust 30-Day Program",
                "goal": "Learn ownership and build a CLI.",
                "audience_level": "Beginner",
                "lesson_style": "Hands-on",
                "daily_time_commitment": "25 minutes",
            },
        )

        created = Course.objects.get(topic=item)
        self.assertRedirects(response, reverse("courses:course_detail", args=[created.id]))
        message = ChatMessage.objects.get(course=created)
        self.assertEqual(message.role, ChatMessage.ASSISTANT)
        self.assertIn("Let's refine your 30-day program", message.content)

    def test_activate_without_outline_shows_error_and_stays_draft(self):
        item = course(with_outline=False)

        response = self.client.post(
            reverse("courses:course_status", args=[item.id, Course.ACTIVE]),
            HTTP_HX_REQUEST="true",
            follow=True,
        )

        item.refresh_from_db()
        self.assertEqual(item.status, Course.DRAFT)
        self.assertContains(response, "Course needs a 30-day outline")

    def test_lesson_markdown_is_sanitized(self):
        generated = lesson()

        response = self.client.get(reverse("courses:lesson_detail", args=[generated.id]))

        self.assertContains(response, "<h1>Lesson</h1>")
        self.assertNotContains(response, "<script>")

    def test_lesson_heading_does_not_duplicate_day_prefix(self):
        item = course(status=Course.ACTIVE)
        generated = Lesson.objects.create(
            course=item,
            day_number=1,
            title="Day 1: What a Piano Is, in Plain Language",
            content_markdown="Useful content.",
            summary="Summary",
        )

        response = self.client.get(reverse("courses:lesson_detail", args=[generated.id]))

        self.assertContains(response, "<h1>Day 1: What a Piano Is, in Plain Language</h1>", html=True)
        self.assertNotContains(response, "Day 1: Day 1:")

    def test_course_detail_highlights_completed_lessons(self):
        item = course(status=Course.ACTIVE)
        completed = lesson(course_item=item, day_number=1)
        incomplete = lesson(course_item=item, day_number=2)
        completed.mark_complete()
        completed.save(update_fields=["completed_at", "updated_at"])

        response = self.client.get(reverse("courses:course_detail", args=[item.id]))

        self.assertContains(response, "lesson-card-completed", count=1)
        self.assertContains(response, f"Day {completed.day_number}: {completed.title}")
        self.assertContains(response, f"Day {incomplete.day_number}: {incomplete.title}")

    def test_lesson_discussion_persists_user_and_assistant_messages(self):
        generated = lesson()

        response = self.client.post(
            reverse("courses:lesson_discussion_submit", args=[generated.id]),
            {"message": "Can you give me a simpler example?"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LessonDiscussionMessage.objects.filter(lesson=generated).count(), 2)
        self.assertContains(response, "Can you give me a simpler example?")
        self.assertContains(response, "A practical way to explore this")

    def test_lesson_discussion_rejects_empty_message(self):
        generated = lesson()

        response = self.client.post(
            reverse("courses:lesson_discussion_submit", args=[generated.id]),
            {"message": ""},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertFalse(LessonDiscussionMessage.objects.filter(lesson=generated).exists())

    def test_quick_feedback_and_comment(self):
        generated = lesson()

        response = self.client.get(
            reverse("courses:lesson_detail", args=[generated.id]),
            {"feedback": LessonFeedback.MORE_PRACTICAL},
        )
        self.assertContains(response, "Confirm Feedback")
        self.assertContains(response, 'Save "More practical"')
        self.assertEqual(generated.feedback.count(), 0)

        response = self.client.post(
            reverse("courses:quick_feedback", args=[generated.id, LessonFeedback.MORE_PRACTICAL]),
            {"comment": "I need more hands-on examples."},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "More practical")
        self.assertContains(response, "I need more hands-on examples.")

        response = self.client.post(
            reverse("courses:comment_submit", args=[generated.id]),
            {"comment": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "Comment cannot be empty")

        response = self.client.post(
            reverse("courses:comment_submit", args=[generated.id]),
            {"comment": "This was too abstract. I need more examples."},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "This was too abstract")
        self.assertEqual(generated.feedback.count(), 2)

    def test_lesson_completion_modal_saves_state_and_optional_note(self):
        generated = lesson()

        response = self.client.get(reverse("courses:lesson_detail", args=[generated.id]), {"completion": "complete"})
        self.assertContains(response, "Complete Lesson")
        self.assertContains(response, "Optional reflection")
        self.assertContains(response, "not completed")
        self.assertFalse(generated.is_completed)

        response = self.client.post(
            reverse("courses:lesson_completion", args=[generated.id]),
            {"action": "complete", "comment": "This clicked after the practice exercise."},
            follow=True,
        )

        generated.refresh_from_db()
        self.assertTrue(generated.is_completed)
        self.assertContains(response, "completed")
        self.assertContains(response, "Completion note")
        self.assertContains(response, "This clicked after the practice exercise.")

    def test_lesson_can_be_marked_incomplete_without_deleting_completion_notes(self):
        generated = lesson()
        self.client.post(
            reverse("courses:lesson_completion", args=[generated.id]),
            {"action": "complete", "comment": "Keep future lessons practical."},
        )

        response = self.client.post(
            reverse("courses:lesson_completion", args=[generated.id]),
            {"action": "incomplete"},
            HTTP_HX_REQUEST="true",
        )

        generated.refresh_from_db()
        self.assertFalse(generated.is_completed)
        self.assertContains(response, "not completed")
        self.assertEqual(generated.feedback.filter(feedback_type=LessonFeedback.COMPLETION_NOTE).count(), 1)

    def test_quick_feedback_is_idempotent_for_same_lesson_and_type(self):
        generated = lesson()

        for _ in range(2):
            response = self.client.post(
                reverse("courses:quick_feedback", args=[generated.id, LessonFeedback.MORE_PRACTICAL]),
                HTTP_HX_REQUEST="true",
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(
            generated.feedback.filter(feedback_type=LessonFeedback.MORE_PRACTICAL).count(),
            1,
        )

    def test_feedback_get_redirects_to_confirmation_modal_without_saving(self):
        generated = lesson()

        response = self.client.get(reverse("courses:quick_feedback", args=[generated.id, LessonFeedback.TOO_HARD]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("courses:lesson_detail", args=[generated.id]) + "?feedback=too_hard#feedback-modal",
        )
        self.assertEqual(generated.feedback.count(), 0)
