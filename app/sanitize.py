"""Markdown rendering with XSS-safe sanitization.

Use ``render_markdown`` for any user-supplied markdown content that will be
displayed in HTML (ticket descriptions, comments, knowledge-base articles).

Output is safe to embed directly in a Jinja template without ``| safe``;
Jinja auto-escaping is bypassed by the filter that wraps this in ``Markup``.
"""
from __future__ import annotations

import bleach
import markdown
from markupsafe import Markup

ALLOWED_TAGS = [
    "p",
    "br",
    "hr",
    "span",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "code",
    "pre",
    "kbd",
    "sup",
    "sub",
    "blockquote",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "del",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "pre": ["class"],
    "span": ["class"],
    "th": ["align"],
    "td": ["align"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto", "data"]


def _set_link_rel(attrs, new=False):
    href = (attrs.get((None, "href")) or "").lower()
    if href.startswith("http"):
        attrs[(None, "rel")] = "noopener noreferrer nofollow"
        attrs[(None, "target")] = "_blank"
    return attrs


_MD_EXTENSIONS = ["fenced_code", "tables", "nl2br", "sane_lists"]
_MD_EXT_CONFIGS = {}


def render_markdown(text: str | None) -> str:
    """Convert a markdown string to sanitized HTML.

    Returns an empty string for falsy input. The output contains only
    whitelisted tags/attributes/protocols — no script, no event handlers,
    no ``javascript:`` URLs.
    """
    if not text:
        return ""
    raw_html = markdown.markdown(
        text,
        extensions=_MD_EXTENSIONS,
        extension_configs=_MD_EXT_CONFIGS,
        output_format="html5",
    )
    cleaned = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    cleaned = bleach.linkify(
        cleaned,
        callbacks=[_set_link_rel],
        skip_tags=["pre", "code"],
        parse_email=True,
    )
    return cleaned


def render_plain_safe(text: str | None) -> Markup:
    """Render plain text safely: escape HTML and convert newlines to <br>."""
    if not text:
        return Markup("")
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return Markup(escaped.replace("\n", "<br>"))


def render_markdown_safe(text: str | None) -> Markup:
    """Jinja filter entry point: render markdown and return safe Markup."""
    return Markup(render_markdown(text))
