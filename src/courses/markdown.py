import bleach
import markdown as markdown_lib


ALLOWED_TAGS = [
    "a",
    "blockquote",
    "code",
    "em",
    "h1",
    "h2",
    "h3",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "ul",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


def render_markdown(markdown_text: str) -> str:
    html = markdown_lib.markdown(markdown_text, extensions=["extra"])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
