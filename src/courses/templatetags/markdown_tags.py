from django import template
from django.utils.safestring import mark_safe

from courses.markdown import render_markdown

register = template.Library()


@register.filter
def markdown_html(value):
    return mark_safe(render_markdown(value or ""))
