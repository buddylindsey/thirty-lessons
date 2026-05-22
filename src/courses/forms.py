from django import forms

from .models import Course, LessonFeedback, Topic


class TopicForm(forms.ModelForm):
    class Meta:
        model = Topic
        fields = ["title", "description"]


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "goal", "audience_level", "lesson_style", "daily_time_commitment"]


class ChatForm(forms.Form):
    message = forms.CharField(label="Message", widget=forms.Textarea(attrs={"rows": 3}))


class CommentForm(forms.Form):
    comment = forms.CharField(label="Comment", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean_comment(self):
        comment = self.cleaned_data["comment"].strip()
        if not comment:
            raise forms.ValidationError("Comment cannot be empty.")
        return comment


class QuickFeedbackForm(forms.Form):
    feedback_type = forms.ChoiceField(choices=LessonFeedback.FEEDBACK_CHOICES)
