from courses.models import Course, Lesson, Topic


def outline():
    return [{"day": day, "title": f"Day {day}", "objective": f"Objective {day}"} for day in range(1, 31)]


def topic(title="Piano History"):
    return Topic.objects.create(title=title, description="A topic")


def course(status=Course.DRAFT, with_outline=True):
    item = Course.objects.create(
        topic=topic(),
        title="Piano History 30-Day Program",
        goal="Understand composers and piano evolution.",
        audience_level="Beginner",
        lesson_style="Practical",
        daily_time_commitment="20 minutes",
        status=status,
        stable_context="Stable context",
        outline=outline() if with_outline else [],
    )
    return item


def lesson(course_item=None, day_number=1):
    course_item = course_item or course(status=Course.ACTIVE)
    return Lesson.objects.create(
        course=course_item,
        day_number=day_number,
        title=f"Lesson {day_number}",
        content_markdown="# Lesson\n\n<script>alert('x')</script>\n\nUseful content.",
        summary=f"Summary {day_number}",
    )
