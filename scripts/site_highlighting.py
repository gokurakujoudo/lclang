"""Render static syntax colors without changing documentation code text."""

from html import escape

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import inherit

# Pygments stubs omit lexer subclasses and leave plugin options unspecified.
from pygments.lexers import get_lexer_by_name  # pyright: ignore[reportUnknownVariableType]
from pygments.lexers.python import PythonLexer  # pyright: ignore[reportMissingTypeStubs]
from pygments.token import Keyword, Operator
from pygments.util import ClassNotFound


class LclLexer(PythonLexer):
    """Extend Python's visual vocabulary for LCL, without validating expressions."""

    tokens = {
        "root": [
            (r"\b(true|false|null)\b", Keyword.Constant),
            (r"\busing\b", Keyword.Namespace),
            (r"\?\?|\?\.|->|!", Operator),
            inherit,
        ]
    }


def highlight_code(source: str, language: str, attributes: str) -> str:
    """Color a fence or defer to Markdown escaping for unrecognized languages."""
    if not language or language == "text":
        return ""
    try:
        lexer = (
            LclLexer(stripnl=False, ensurenl=False)
            if language in {"lcl", "lclcfg"}
            else get_lexer_by_name(language, stripnl=False, ensurenl=False)
        )
    except ClassNotFound:
        return ""
    return highlight(source, lexer, HtmlFormatter(nowrap=True))


def format_fence(
    source: str,
    language: str,
    css_class: str,
    options: dict[str, object],
    md: object,
    **kwargs: object,
) -> str:
    """Restore SuperFences' removed line terminator before highlighting exact source."""
    source += "\n"
    content = highlight_code(source, language, "") or escape(source)
    return (
        f'<div class="highlight"><pre><code class="language-{escape(language, quote=True)}">'
        f"{content}</code></pre></div>"
    )
