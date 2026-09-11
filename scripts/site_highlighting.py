"""Render static syntax colors without changing documentation code text."""

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import inherit
from pygments.lexers import get_lexer_by_name
from pygments.lexers.python import PythonLexer
from pygments.token import Keyword, Operator
from pygments.util import ClassNotFound


class LclLexer(PythonLexer):
    """Extend Python's visual vocabulary for LCL, without validating expressions."""

    tokens = {"root": [
        (r"\b(true|false|null)\b", Keyword.Constant),
        (r"\busing\b", Keyword.Namespace),
        (r"\?\?|\?\.|->|!", Operator),
        inherit,
    ]}


def highlight_code(source: str, language: str, attributes: str) -> str:
    """Color a fence or defer to Markdown escaping for unrecognized languages."""
    if not language or language == "text":
        return ""
    try:
        lexer = (LclLexer(stripnl=False, ensurenl=False) if language in {"lcl", "lclcfg"}
                 else get_lexer_by_name(language, stripnl=False, ensurenl=False))
    except ClassNotFound:
        return ""
    return highlight(source, lexer, HtmlFormatter(nowrap=True))
