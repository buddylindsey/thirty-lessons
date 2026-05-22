from django.contrib import admin

from .models import ChatMessage, Course, CourseMemory, Lesson, LessonFeedback, Topic


class CourseInline(admin.TabularInline):
    model = Course
    fields = ("title", "status", "audience_level", "daily_time_commitment", "created_at")
    readonly_fields = ("created_at",)
    extra = 0
    show_change_link = True


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "course_count", "created_at", "updated_at")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
    inlines = (CourseInline,)

    @admin.display(description="Courses")
    def course_count(self, obj):
        return obj.courses.count()


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    fields = ("role", "content", "created_at")
    readonly_fields = ("created_at",)
    extra = 0
    show_change_link = True


class LessonInline(admin.TabularInline):
    model = Lesson
    fields = ("day_number", "title", "summary", "email_sent_at", "generated_at")
    readonly_fields = ("generated_at",)
    extra = 0
    show_change_link = True


class CourseMemoryInline(admin.StackedInline):
    model = CourseMemory
    fields = ("content", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    extra = 0
    max_num = 1
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "topic",
        "status",
        "lesson_count",
        "has_outline",
        "started_at",
        "completed_at",
        "updated_at",
    )
    list_filter = ("status", "topic", "created_at", "updated_at")
    search_fields = ("title", "goal", "topic__title", "stable_context")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at")
    autocomplete_fields = ("topic",)
    fieldsets = (
        (None, {"fields": ("topic", "title", "status")}),
        (
            "Learning Plan",
            {
                "fields": (
                    "goal",
                    "audience_level",
                    "lesson_style",
                    "daily_time_commitment",
                    "stable_context",
                    "outline",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at", "started_at", "completed_at")}),
    )
    inlines = (CourseMemoryInline, LessonInline, ChatMessageInline)

    @admin.display(boolean=True, description="Outline")
    def has_outline(self, obj):
        return obj.has_valid_outline()

    @admin.display(description="Lessons")
    def lesson_count(self, obj):
        return obj.lessons.count()


class LessonFeedbackInline(admin.TabularInline):
    model = LessonFeedback
    fields = ("feedback_type", "comment", "created_at")
    readonly_fields = ("created_at",)
    extra = 0
    show_change_link = True


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "day_number", "email_sent_at", "generated_at", "updated_at")
    list_filter = ("course", "day_number", "email_sent_at", "generated_at")
    search_fields = ("title", "summary", "content_markdown", "course__title", "course__topic__title")
    readonly_fields = ("created_at", "updated_at", "generated_at")
    autocomplete_fields = ("course",)
    inlines = (LessonFeedbackInline,)
    ordering = ("course", "day_number")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("course", "role", "short_content", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "course__title", "course__topic__title")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("course",)

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80]


@admin.register(LessonFeedback)
class LessonFeedbackAdmin(admin.ModelAdmin):
    list_display = ("lesson", "feedback_type", "short_comment", "created_at")
    list_filter = ("feedback_type", "created_at")
    search_fields = ("comment", "lesson__title", "lesson__course__title")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("lesson",)

    @admin.display(description="Comment")
    def short_comment(self, obj):
        return obj.comment[:80]


@admin.register(CourseMemory)
class CourseMemoryAdmin(admin.ModelAdmin):
    list_display = ("course", "updated_at", "created_at")
    search_fields = ("content", "course__title", "course__topic__title")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("course",)
