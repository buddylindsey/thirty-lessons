from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Topic(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    DRAFT = Status.DRAFT
    ACTIVE = Status.ACTIVE
    PAUSED = Status.PAUSED
    COMPLETED = Status.COMPLETED
    ARCHIVED = Status.ARCHIVED

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="courses")
    title = models.CharField(max_length=200)
    goal = models.TextField()
    audience_level = models.CharField(max_length=100)
    lesson_style = models.CharField(max_length=100)
    daily_time_commitment = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    stable_context = models.TextField(blank=True)
    outline = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def has_valid_outline(self):
        if not isinstance(self.outline, list) or len(self.outline) != 30:
            return False
        for expected_day, item in enumerate(self.outline, start=1):
            if not isinstance(item, dict):
                return False
            if item.get("day") != expected_day:
                return False
            if not isinstance(item.get("title"), str) or not item["title"].strip():
                return False
            if not isinstance(item.get("objective"), str) or not item["objective"].strip():
                return False
        return True

    def activate(self):
        if not self.has_valid_outline():
            raise ValidationError("Course needs a 30-day outline before activation.")
        self.status = self.Status.ACTIVE
        if self.started_at is None:
            self.started_at = timezone.now()

    def pause(self):
        if self.status == self.Status.ACTIVE:
            self.status = self.Status.PAUSED

    def complete(self):
        self.status = self.Status.COMPLETED
        if self.completed_at is None:
            self.completed_at = timezone.now()

    def archive(self):
        self.status = self.Status.ARCHIVED


class ChatMessage(models.Model):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ROLE_CHOICES = [(USER, "User"), (ASSISTANT, "Assistant"), (SYSTEM, "System")]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="chat_messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    day_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    content_markdown = models.TextField()
    summary = models.TextField()
    email_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_number"]
        constraints = [
            models.UniqueConstraint(fields=["course", "day_number"], name="unique_lesson_per_course_day")
        ]

    def __str__(self):
        return f"Day {self.day_number}: {self.title}"

    @property
    def is_completed(self):
        return self.completed_at is not None

    def mark_complete(self):
        if self.completed_at is None:
            self.completed_at = timezone.now()

    def mark_incomplete(self):
        self.completed_at = None


class LessonDiscussionMessage(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="discussion_messages")
    role = models.CharField(max_length=20, choices=ChatMessage.ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class LessonFeedback(models.Model):
    TOO_EASY = "too_easy"
    TOO_HARD = "too_hard"
    GOOD_PACING = "good_pacing"
    MORE_PRACTICAL = "more_practical"
    MORE_THEORY = "more_theory"
    MORE_EXAMPLES = "more_examples"
    CONFUSING = "confusing"
    SKIP_AHEAD = "skip_ahead"
    CUSTOM_COMMENT = "custom_comment"
    COMPLETION_NOTE = "completion_note"
    FEEDBACK_CHOICES = [
        (TOO_EASY, "Too easy"),
        (TOO_HARD, "Too hard"),
        (GOOD_PACING, "Good pacing"),
        (MORE_PRACTICAL, "More practical"),
        (MORE_THEORY, "More theory"),
        (MORE_EXAMPLES, "More examples"),
        (CONFUSING, "Confusing"),
        (SKIP_AHEAD, "Skip ahead"),
        (CUSTOM_COMMENT, "Comment"),
        (COMPLETION_NOTE, "Completion note"),
    ]

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="feedback")
    feedback_type = models.CharField(max_length=40, choices=FEEDBACK_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class CourseMemory(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="memory")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Memory for {self.course}"
