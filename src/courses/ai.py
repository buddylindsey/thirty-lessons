import json

from django.conf import settings


class AIProvider:
    def generate_initial_course_message(self, context: dict) -> str:
        raise NotImplementedError

    def generate_chat_response(self, messages: list[dict]) -> str:
        raise NotImplementedError

    def generate_course_outline(self, context: dict) -> list[dict]:
        raise NotImplementedError

    def generate_daily_lesson(self, context: dict) -> dict:
        raise NotImplementedError

    def generate_lesson_discussion_response(self, context: dict) -> str:
        raise NotImplementedError

    def update_course_memory(self, context: dict) -> str:
        raise NotImplementedError


class FakeAIProvider(AIProvider):
    def generate_initial_course_message(self, context: dict) -> str:
        course = context["course"]
        topic = context["topic"]
        return (
            f"Let's refine your 30-day program for **{topic['title']}**.\n\n"
            f"I see the goal is: {course['goal']}\n\n"
            "Before generating the outline, a few choices would help shape the course:\n\n"
            "- Should the daily lessons lean more practical, historical, conceptual, or project-based?\n"
            "- Are there any subtopics you definitely want included or avoided?\n"
            "- By day 30, what should feel noticeably easier or clearer?"
        )

    def generate_chat_response(self, messages: list[dict]) -> str:
        latest = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return (
            f"I will use that direction for the course: {latest}\n\n"
            "A useful next step is to choose the angle for the outline. Should this focus more on "
            "mechanical inventions, major historical periods, makers and manufacturing, or the "
            "specific path from early keyboard instruments to the modern grand piano?"
        )

    def generate_course_outline(self, context: dict) -> list[dict]:
        topic = context["topic"]["title"]
        return [
            {
                "day": day,
                "title": f"{topic} - Day {day}",
                "objective": f"Build understanding of {topic} step {day}.",
            }
            for day in range(1, 31)
        ]

    def generate_daily_lesson(self, context: dict) -> dict:
        day = context["day_number"]
        outline_item = context["outline_item"]
        title = outline_item.get("title") or f"Day {day}"
        return {
            "title": title,
            "content_markdown": (
                f"# {title}\n\n"
                f"Today you will work on {outline_item.get('objective', title)}.\n\n"
                "## Practice\n\nWrite down one insight and one question before tomorrow."
            ),
            "summary": f"Covered {title} with a short practice prompt.",
        }

    def generate_lesson_discussion_response(self, context: dict) -> str:
        latest = next((m["content"] for m in reversed(context.get("discussion_history", [])) if m["role"] == "user"), "")
        lesson = context["lesson"]
        return (
            f"Let's extend **{lesson['title']}** around your question: {latest}\n\n"
            "A practical way to explore this is to restate the idea in your own words, then try one "
            "small example before moving on."
        )

    def update_course_memory(self, context: dict) -> str:
        feedback = context.get("feedback", [])
        if not feedback:
            return "No recurring preferences yet."
        themes = ", ".join(sorted({item["feedback_type"] for item in feedback}))
        return f"Recurring learner feedback themes: {themes}."


class AIProviderError(Exception):
    pass


class OpenAIProvider(AIProvider):
    def __init__(self, api_key=None, model=None, client=None):
        self.model = model or settings.OPENAI_MODEL
        if client is not None:
            self.client = client
            return
        api_key = api_key or settings.OPENAI_KEY
        if not api_key:
            raise AIProviderError("OPENAI_KEY is required for the OpenAI provider.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIProviderError("The openai package is not installed.") from exc
        self.client = OpenAI(api_key=api_key)

    def generate_initial_course_message(self, context: dict) -> str:
        return self._text_response(
            "You are starting a guided refinement conversation for a personal 30-day learning program. "
            "Use the supplied topic and course settings to write the first assistant message. "
            "Acknowledge the learner's goal briefly, then ask 2 or 3 targeted questions that would "
            "materially improve the eventual 30-day outline. Do not generate the outline yet. "
            "Format the response as readable markdown with short paragraphs or bullets.",
            json.dumps(context, default=str),
        )

    def generate_chat_response(self, messages: list[dict]) -> str:
        conversation = [
            {"role": self._message_role(item["role"]), "content": item["content"]}
            for item in messages
            if item.get("role") in {"user", "assistant", "system"} and item.get("content")
        ]
        return self._text_response(
            "You are a course-design partner for a self-paced 30-day learning program. "
            "Have a real planning conversation before an outline is generated. "
            "Help the learner explore possible course directions, tradeoffs, exclusions, "
            "depth, chronology, technical level, and preferred daily lesson style. "
            "When the learner gives a preference, briefly reflect it back as a concrete design choice. "
            "Then ask 2 or 3 targeted follow-up questions that would materially improve the eventual outline. "
            "Do not generate the full 30-day outline in chat. Keep the response concise and practical. "
            "Format the response as readable markdown with short paragraphs or bullets.",
            conversation,
        )

    def generate_course_outline(self, context: dict) -> list[dict]:
        data = self._json_response(
            "Create exactly 30 course outline items. Return JSON only.",
            context,
            {
                "type": "object",
                "properties": {
                    "outline": {
                        "type": "array",
                        "minItems": 30,
                        "maxItems": 30,
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "integer"},
                                "title": {"type": "string"},
                                "objective": {"type": "string"},
                            },
                            "required": ["day", "title", "objective"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["outline"],
                "additionalProperties": False,
            },
        )
        return data["outline"]

    def generate_daily_lesson(self, context: dict) -> dict:
        return self._json_response(
            "Generate one daily lesson using the supplied bounded course context. "
            "Return markdown content suitable for email and web display.",
            context,
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content_markdown": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["title", "content_markdown", "summary"],
                "additionalProperties": False,
            },
        )

    def generate_lesson_discussion_response(self, context: dict) -> str:
        return self._text_response(
            "You are helping a learner extend and understand a single lesson from a personal "
            "30-day course. Answer the learner's latest question using the supplied lesson, course, "
            "recent lesson summaries, feedback, memory, and discussion history. Stay focused on the "
            "current lesson unless the learner asks for broader connections. Prefer concrete examples, "
            "short explanations, and small practice prompts. Do not generate a replacement full lesson "
            "unless explicitly asked. Format the response as readable markdown.",
            json.dumps(context, default=str),
        )

    def update_course_memory(self, context: dict) -> str:
        return self._text_response(
            "Compress the learner's repeated preferences, struggles, pacing notes, "
            "and useful future-generation guidance into a short course memory.",
            json.dumps(context, default=str),
        )

    def _text_response(self, instructions: str, prompt: str) -> str:
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=prompt,
            )
        except Exception as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc
        text = getattr(response, "output_text", "").strip()
        if not text:
            raise AIProviderError("OpenAI returned an empty response.")
        return text

    def _message_role(self, role: str) -> str:
        if role == "system":
            return "developer"
        if role == "assistant":
            return "assistant"
        return "user"

    def _json_response(self, instructions: str, context: dict, schema: dict) -> dict:
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                input=json.dumps(context, default=str),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "learning_program_response",
                        "schema": schema,
                        "strict": False,
                    }
                },
            )
        except Exception as exc:
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc
        raw = getattr(response, "output_text", "").strip()
        if not raw:
            raise AIProviderError("OpenAI returned an empty JSON response.")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderError("OpenAI returned invalid JSON.") from exc


_provider_override = None


def get_ai_provider() -> AIProvider:
    if _provider_override is not None:
        return _provider_override
    if settings.AI_PROVIDER == "openai":
        return OpenAIProvider()
    return FakeAIProvider()


def set_ai_provider(provider: AIProvider | None):
    global _provider_override
    _provider_override = provider
