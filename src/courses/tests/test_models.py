from django.core.exceptions import ValidationError
from django.test import TestCase

from courses.models import Course, Topic
from courses.tests.factories import course, lesson


class ModelTests(TestCase):
    def test_empty_topic_title_is_rejected(self):
        topic = Topic(title="")

        with self.assertRaises(ValidationError):
            topic.full_clean()

    def test_duplicate_topic_titles_are_allowed(self):
        Topic.objects.create(title="Piano History")
        Topic.objects.create(title="Piano History")

        self.assertEqual(Topic.objects.filter(title="Piano History").count(), 2)

    def test_activation_requires_valid_outline(self):
        item = course(with_outline=False)

        with self.assertRaises(ValidationError):
            item.activate()

    def test_activation_rejects_malformed_outline_items(self):
        item = course(with_outline=True)
        item.outline[0] = {"day": 1, "title": "", "objective": "Objective 1"}

        with self.assertRaises(ValidationError):
            item.activate()

    def test_activation_sets_started_at(self):
        item = course(with_outline=True)

        item.activate()

        self.assertEqual(item.status, Course.ACTIVE)
        self.assertIsNotNone(item.started_at)

    def test_lesson_completion_helpers_set_and_clear_completed_at(self):
        generated = lesson()

        generated.mark_complete()

        self.assertTrue(generated.is_completed)
        self.assertIsNotNone(generated.completed_at)

        generated.mark_incomplete()

        self.assertFalse(generated.is_completed)
        self.assertIsNone(generated.completed_at)
