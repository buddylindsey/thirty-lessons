import json
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from courses.ai import FakeAIProvider, OpenAIProvider, get_ai_provider, set_ai_provider


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeOpenAIClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


class OpenAIProviderTests(SimpleTestCase):
    def tearDown(self):
        set_ai_provider(None)

    @override_settings(AI_PROVIDER="fake", OPENAI_KEY="")
    def test_provider_defaults_to_fake_without_key(self):
        self.assertIsInstance(get_ai_provider(), FakeAIProvider)

    @override_settings(AI_PROVIDER="openai", OPENAI_KEY="test-key", OPENAI_MODEL="test-model")
    def test_provider_uses_openai_when_configured(self):
        self.assertIsInstance(get_ai_provider(), OpenAIProvider)

    def test_openai_initial_message_uses_course_context(self):
        client = FakeOpenAIClient("What would you like to emphasize?")
        provider = OpenAIProvider(client=client, model="test-model")

        response = provider.generate_initial_course_message(
            {
                "topic": {"title": "Piano History", "description": "A topic"},
                "course": {
                    "title": "Piano History 30-Day Program",
                    "goal": "Understand composers.",
                    "audience_level": "Beginner",
                    "lesson_style": "Practical",
                    "daily_time_commitment": "20 minutes",
                    "stable_context": "Stable context",
                },
            }
        )

        self.assertEqual(response, "What would you like to emphasize?")
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertIn("starting a guided refinement conversation", call["instructions"])
        self.assertIn("Piano History", call["input"])

    def test_openai_chat_uses_responses_api(self):
        client = FakeOpenAIClient("A concise response.")
        provider = OpenAIProvider(client=client, model="test-model")

        response = provider.generate_chat_response([{"role": "user", "content": "Help me learn piano."}])

        self.assertEqual(response, "A concise response.")
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertIn("course-design partner", call["instructions"])
        self.assertEqual(call["input"][0]["content"], "Help me learn piano.")

    def test_openai_outline_parses_structured_output(self):
        outline = [
            {"day": day, "title": f"Day {day}", "objective": f"Objective {day}"}
            for day in range(1, 31)
        ]
        client = FakeOpenAIClient(json.dumps({"outline": outline}))
        provider = OpenAIProvider(client=client, model="test-model")

        result = provider.generate_course_outline({"topic": {"title": "Piano"}})

        self.assertEqual(len(result), 30)
        call = client.responses.calls[0]
        self.assertEqual(call["text"]["format"]["type"], "json_schema")

    def test_openai_lesson_parses_structured_output(self):
        client = FakeOpenAIClient(
            json.dumps({"title": "Day 1", "content_markdown": "# Day 1", "summary": "Summary"})
        )
        provider = OpenAIProvider(client=client, model="test-model")

        result = provider.generate_daily_lesson({"day_number": 1})

        self.assertEqual(result["title"], "Day 1")
        self.assertEqual(result["content_markdown"], "# Day 1")
