from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from .ai import AIProviderError
from .forms import ChatForm, CommentForm, CourseForm, QuickFeedbackForm, TopicForm
from .markdown import render_markdown
from .models import ChatMessage, Course, Lesson, LessonFeedback, Topic
from .services import GenerationError, generate_outline, get_ai_provider, start_course_conversation


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


class TopicListView(ListView):
    model = Topic
    template_name = "courses/topic_list.html"
    context_object_name = "topics"

    def get_queryset(self):
        return Topic.objects.prefetch_related("courses")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_courses"] = (
            Course.objects.filter(status=Course.Status.ACTIVE).select_related("topic").prefetch_related("lessons")
        )
        return context


class TopicCreateView(CreateView):
    model = Topic
    form_class = TopicForm
    template_name = "courses/topic_form.html"

    def get_success_url(self):
        return reverse("courses:topic_detail", args=[self.object.id])


class TopicDetailView(DetailView):
    model = Topic
    template_name = "courses/topic_detail.html"
    context_object_name = "topic"
    pk_url_kwarg = "topic_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["courses"] = self.object.courses.prefetch_related("lessons")
        return context


class CourseCreateView(CreateView):
    model = Course
    form_class = CourseForm
    template_name = "courses/course_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.topic = get_object_or_404(Topic, id=kwargs["topic_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"title": f"{self.topic.title} 30-Day Program"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["topic"] = self.topic
        return context

    def form_valid(self, form):
        course = form.save(commit=False)
        course.topic = self.topic
        course.status = Course.Status.DRAFT
        course.stable_context = (
            f"Goal: {course.goal}\n"
            f"Level: {course.audience_level}\n"
            f"Style: {course.lesson_style}\n"
            f"Daily time: {course.daily_time_commitment}"
        )
        course.save()
        self.object = course
        try:
            start_course_conversation(course)
        except GenerationError as exc:
            messages.warning(
                self.request,
                f"Course created, but the assistant could not start the refinement chat: {exc}",
            )
        return redirect("courses:course_detail", course.id)


class CourseDetailView(DetailView):
    model = Course
    template_name = "courses/course_detail.html"
    context_object_name = "course"
    pk_url_kwarg = "course_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "chat_form": ChatForm(),
                "ai_provider_name": settings.AI_PROVIDER,
                "openai_key_configured": bool(settings.OPENAI_KEY),
            }
        )
        return context


class ChatSubmitView(View):
    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        form = ChatForm(request.POST or None)
        if not form.is_valid():
            return HttpResponseBadRequest("Invalid chat message.")
        ChatMessage.objects.create(course=course, role=ChatMessage.USER, content=form.cleaned_data["message"])
        messages_for_ai = [
            {
                "role": ChatMessage.SYSTEM,
                "content": (
                    f"Topic: {course.topic.title}\n"
                    f"Topic description: {course.topic.description or 'None'}\n"
                    f"Course title: {course.title}\n"
                    f"Goal: {course.goal}\n"
                    f"Audience level: {course.audience_level}\n"
                    f"Lesson style: {course.lesson_style}\n"
                    f"Daily time commitment: {course.daily_time_commitment}\n"
                    "Use this chat to refine what the learner wants before outline generation."
                ),
            }
        ]
        messages_for_ai.extend(course.chat_messages.values("role", "content"))
        try:
            response = get_ai_provider().generate_chat_response(messages_for_ai)
        except AIProviderError as exc:
            messages.error(request, str(exc))
        else:
            ChatMessage.objects.create(course=course, role=ChatMessage.ASSISTANT, content=response)
        if is_htmx(request):
            return render(request, "courses/partials/chat_panel.html", {"course": course, "chat_form": ChatForm()})
        return redirect("courses:course_detail", course.id)


class OutlineGenerateView(View):
    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        try:
            generate_outline(course)
            messages.success(request, "Outline generated.")
        except GenerationError as exc:
            messages.error(request, str(exc))
        course.refresh_from_db()
        if is_htmx(request):
            return render(request, "courses/partials/outline_panel.html", {"course": course})
        return redirect("courses:course_detail", course.id)


class CourseStatusView(View):
    status_handlers = {
        Course.Status.ACTIVE: "activate",
        Course.Status.PAUSED: "pause",
        Course.Status.COMPLETED: "complete",
        Course.Status.ARCHIVED: "archive",
    }

    def post(self, request, course_id, status):
        course = get_object_or_404(Course, id=course_id)
        handler_name = self.status_handlers.get(status)
        if handler_name is None:
            return HttpResponseBadRequest("Invalid status.")
        try:
            getattr(course, handler_name)()
            course.save()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        course.refresh_from_db()
        if is_htmx(request):
            return render(request, "courses/partials/status_panel.html", {"course": course})
        return redirect("courses:course_detail", course.id)


class CourseListView(ListView):
    model = Course
    template_name = "courses/course_list.html"
    context_object_name = "courses"
    status = None
    title = "Courses"

    def get_queryset(self):
        return Course.objects.filter(status=self.status).select_related("topic").prefetch_related("lessons")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class ActiveCourseListView(CourseListView):
    status = Course.Status.ACTIVE
    title = "Active Courses"


class ArchivedCourseListView(CourseListView):
    status = Course.Status.ARCHIVED
    title = "Archived Courses"


class LessonDetailView(DetailView):
    model = Lesson
    template_name = "courses/lesson_detail.html"
    context_object_name = "lesson"
    pk_url_kwarg = "lesson_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "content_html": render_markdown(self.object.content_markdown),
                "comment_form": CommentForm(),
                "feedback_choices": LessonFeedback.FEEDBACK_CHOICES,
            }
        )
        return context


class QuickFeedbackView(View):
    def get(self, request, lesson_id, feedback_type):
        return self.create_feedback(request, lesson_id, feedback_type)

    def post(self, request, lesson_id, feedback_type):
        return self.create_feedback(request, lesson_id, feedback_type)

    def create_feedback(self, request, lesson_id, feedback_type):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        form = QuickFeedbackForm({"feedback_type": feedback_type})
        if not form.is_valid():
            return HttpResponseBadRequest("Invalid feedback type.")
        LessonFeedback.objects.get_or_create(lesson=lesson, feedback_type=form.cleaned_data["feedback_type"])
        if is_htmx(request):
            return render(
                request,
                "courses/partials/feedback_panel.html",
                {"lesson": lesson, "comment_form": CommentForm(), "feedback_choices": LessonFeedback.FEEDBACK_CHOICES},
            )
        return redirect("courses:lesson_detail", lesson.id)


class CommentSubmitView(View):
    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        form = CommentForm(request.POST or None)
        if form.is_valid():
            LessonFeedback.objects.create(
                lesson=lesson,
                feedback_type=LessonFeedback.CUSTOM_COMMENT,
                comment=form.cleaned_data["comment"],
            )
            if is_htmx(request):
                return render(
                    request,
                    "courses/partials/feedback_panel.html",
                    {
                        "lesson": lesson,
                        "comment_form": CommentForm(),
                        "feedback_choices": LessonFeedback.FEEDBACK_CHOICES,
                    },
                )
            return redirect("courses:lesson_detail", lesson.id)
        if is_htmx(request):
            return render(
                request,
                "courses/partials/feedback_panel.html",
                {"lesson": lesson, "comment_form": form, "feedback_choices": LessonFeedback.FEEDBACK_CHOICES},
            )
        return render(
            request,
            "courses/lesson_detail.html",
            {
                "lesson": lesson,
                "content_html": render_markdown(lesson.content_markdown),
                "comment_form": form,
                "feedback_choices": LessonFeedback.FEEDBACK_CHOICES,
            },
        )
