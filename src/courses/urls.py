from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.TopicListView.as_view(), name="topic_list"),
    path("topics/new/", views.TopicCreateView.as_view(), name="topic_create"),
    path("topics/<int:topic_id>/", views.TopicDetailView.as_view(), name="topic_detail"),
    path("topics/<int:topic_id>/courses/new/", views.CourseCreateView.as_view(), name="course_create"),
    path("courses/active/", views.ActiveCourseListView.as_view(), name="active_courses"),
    path("courses/archive/", views.ArchivedCourseListView.as_view(), name="archived_courses"),
    path("courses/<int:course_id>/", views.CourseDetailView.as_view(), name="course_detail"),
    path("courses/<int:course_id>/chat/", views.ChatSubmitView.as_view(), name="chat_submit"),
    path("courses/<int:course_id>/outline/", views.OutlineGenerateView.as_view(), name="outline_generate"),
    path("courses/<int:course_id>/status/<str:status>/", views.CourseStatusView.as_view(), name="course_status"),
    path("lessons/<int:lesson_id>/", views.LessonDetailView.as_view(), name="lesson_detail"),
    path("lessons/<int:lesson_id>/discussion/", views.LessonDiscussionSubmitView.as_view(), name="lesson_discussion_submit"),
    path("lessons/<int:lesson_id>/completion/", views.LessonCompletionView.as_view(), name="lesson_completion"),
    path(
        "lessons/<int:lesson_id>/feedback/<str:feedback_type>/",
        views.QuickFeedbackView.as_view(),
        name="quick_feedback",
    ),
    path("lessons/<int:lesson_id>/comments/", views.CommentSubmitView.as_view(), name="comment_submit"),
]
