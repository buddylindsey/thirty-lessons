import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils.html import escape
from django.utils.http import urlencode
from django.utils import timezone

from .ai import AIProviderError, get_ai_provider
from .markdown import render_markdown
from .models import ChatMessage, Course, CourseMemory, Lesson, LessonFeedback

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    pass


def require_non_empty_string(value, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GenerationError(f"AI provider returned an invalid {field_name}.")
    return value.strip()


def validate_outline(outline) -> list[dict]:
    if not isinstance(outline, list) or len(outline) != 30:
        raise GenerationError("AI provider returned an invalid outline.")
    normalized = []
    for expected_day, item in enumerate(outline, start=1):
        if not isinstance(item, dict):
            raise GenerationError("AI provider returned an invalid outline.")
        day = item.get("day")
        if day != expected_day:
            raise GenerationError("AI provider returned an invalid outline.")
        normalized.append(
            {
                "day": day,
                "title": require_non_empty_string(item.get("title"), "outline title"),
                "objective": require_non_empty_string(item.get("objective"), "outline objective"),
            }
        )
    return normalized


def validate_lesson_data(data) -> dict:
    if not isinstance(data, dict):
        raise GenerationError("AI provider returned an invalid lesson.")
    return {
        "title": require_non_empty_string(data.get("title"), "lesson title"),
        "content_markdown": require_non_empty_string(data.get("content_markdown"), "lesson content"),
        "summary": require_non_empty_string(data.get("summary"), "lesson summary"),
    }


def course_context(course: Course) -> dict:
    return {
        "topic": {"title": course.topic.title, "description": course.topic.description},
        "course": {
            "title": course.title,
            "goal": course.goal,
            "audience_level": course.audience_level,
            "lesson_style": course.lesson_style,
            "daily_time_commitment": course.daily_time_commitment,
            "stable_context": course.stable_context,
        },
    }


def generate_outline(course: Course):
    messages = list(course.chat_messages.values("role", "content", "created_at"))
    context = {**course_context(course), "chat_history": messages}
    try:
        outline = get_ai_provider().generate_course_outline(context)
    except AIProviderError as exc:
        raise GenerationError(str(exc)) from exc
    outline = validate_outline(outline)
    course.outline = outline
    course.save(update_fields=["outline", "updated_at"])
    return outline


def start_course_conversation(course: Course) -> ChatMessage:
    context = course_context(course)
    try:
        message = get_ai_provider().generate_initial_course_message(context)
    except AIProviderError as exc:
        raise GenerationError(str(exc)) from exc
    message = require_non_empty_string(message, "initial chat message")
    return ChatMessage.objects.create(course=course, role=ChatMessage.ASSISTANT, content=message)


def build_daily_lesson_context(course: Course, day_number: int) -> dict:
    if not course.has_valid_outline():
        raise GenerationError("Course does not have a valid outline.")
    recent_lessons = list(
        course.lessons.filter(day_number__lt=day_number)
        .order_by("-day_number")
        .values("day_number", "title", "summary")[:3]
    )
    recent_lessons.reverse()
    recent_feedback = list(
        LessonFeedback.objects.filter(lesson__course=course, lesson__day_number__lt=day_number)
        .order_by("-created_at")
        .values("feedback_type", "comment", "lesson__day_number")[:10]
    )
    memory = getattr(course, "memory", None)
    return {
        **course_context(course),
        "outline": course.outline,
        "day_number": day_number,
        "outline_item": course.outline[day_number - 1],
        "recent_lessons": recent_lessons,
        "recent_feedback": recent_feedback,
        "course_memory": memory.content if memory else "",
    }


def next_missing_day(course: Course) -> int | None:
    existing = set(course.lessons.values_list("day_number", flat=True))
    for day in range(1, 31):
        if day not in existing:
            return day
    return None


def generate_next_lesson(course: Course, send_email=True) -> Lesson | None:
    if course.status != Course.Status.ACTIVE:
        return None
    if course.lessons.filter(generated_at__date=timezone.localdate()).exists():
        logger.info("Course %s already has a lesson generated today.", course.id)
        return None
    day_number = next_missing_day(course)
    if day_number is None:
        course.complete()
        course.save(update_fields=["status", "completed_at", "updated_at"])
        return None

    context = build_daily_lesson_context(course, day_number)
    try:
        data = get_ai_provider().generate_daily_lesson(context)
    except AIProviderError as exc:
        raise GenerationError(str(exc)) from exc
    data = validate_lesson_data(data)

    try:
        with transaction.atomic():
            lesson = Lesson.objects.create(
                course=course,
                day_number=day_number,
                title=data["title"],
                content_markdown=data["content_markdown"],
                summary=data["summary"],
            )
    except IntegrityError:
        logger.info("Lesson already exists for course=%s day=%s", course.id, day_number)
        return course.lessons.get(day_number=day_number)

    if send_email:
        try:
            send_lesson_email(lesson)
        except Exception:
            logger.exception("Failed sending lesson email for lesson=%s", lesson.id)
    return lesson


def feedback_url(lesson: Lesson, feedback_type: str) -> str:
    return (
        settings.SITE_BASE_URL
        + reverse("courses:lesson_detail", args=[lesson.id])
        + "?"
        + urlencode({"feedback": feedback_type})
        + "#feedback-modal"
    )


def lesson_url(lesson: Lesson) -> str:
    return settings.SITE_BASE_URL + reverse("courses:lesson_detail", args=[lesson.id])


def lesson_email_title(lesson: Lesson) -> str:
    title = lesson.title.strip()
    if re.match(rf"^day\s+{lesson.day_number}\s*:", title, flags=re.IGNORECASE):
        return title
    return f"Day {lesson.day_number}: {title}"


def lesson_email_markdown(lesson: Lesson) -> str:
    title = lesson_email_title(lesson)
    lines = lesson.content_markdown.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match and match.group(1).strip().lower() in {title.lower(), lesson.title.strip().lower()}:
            return "\n".join(lines[index + 1 :]).lstrip()
        return lesson.content_markdown
    return lesson.content_markdown


def lesson_email_text_body(lesson: Lesson) -> str:
    body = [
        lesson_email_title(lesson),
        "",
        lesson_email_markdown(lesson),
        "",
        f"View lesson: {lesson_url(lesson)}",
        "",
        "Quick feedback:",
    ]
    for feedback_type, label in LessonFeedback.FEEDBACK_CHOICES:
        if feedback_type != LessonFeedback.CUSTOM_COMMENT:
            body.append(f"{label}: {feedback_url(lesson, feedback_type)}")
    return "\n".join(body)


def lesson_email_html_body(lesson: Lesson) -> str:
    feedback_links = []
    for feedback_type, label in LessonFeedback.FEEDBACK_CHOICES:
        if feedback_type != LessonFeedback.CUSTOM_COMMENT:
            feedback_links.append(
                f'<li><a href="{escape(feedback_url(lesson, feedback_type))}">{escape(label)}</a></li>'
            )
    return "\n".join(
        [
            f"<h1>{escape(lesson_email_title(lesson))}</h1>",
            render_markdown(lesson_email_markdown(lesson)),
            f'<p><a href="{escape(lesson_url(lesson))}">View lesson</a></p>',
            "<h2>Quick feedback</h2>",
            "<ul>",
            *feedback_links,
            "</ul>",
        ]
    )


def send_lesson_email(lesson: Lesson):
    email = EmailMultiAlternatives(
        subject=lesson_email_title(lesson),
        body=lesson_email_text_body(lesson),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.LESSON_RECIPIENT_EMAIL],
    )
    email.attach_alternative(lesson_email_html_body(lesson), "text/html")
    email.send(fail_silently=False)
    lesson.email_sent_at = timezone.now()
    lesson.save(update_fields=["email_sent_at", "updated_at"])


def update_memory(course: Course) -> CourseMemory:
    context = {
        **course_context(course),
        "lesson_summaries": list(course.lessons.values("day_number", "title", "summary")),
        "feedback": list(
            LessonFeedback.objects.filter(lesson__course=course).values("feedback_type", "comment")
        ),
        "current_memory": getattr(course, "memory", None).content if hasattr(course, "memory") else "",
    }
    try:
        content = get_ai_provider().update_course_memory(context)
    except AIProviderError as exc:
        raise GenerationError(str(exc)) from exc
    content = require_non_empty_string(content, "course memory")
    memory, _ = CourseMemory.objects.update_or_create(course=course, defaults={"content": content})
    return memory
