"""Canonical rendering for atoms and semantic f-string nodes."""

from __future__ import annotations

from lclang.ast import (
    LclAstNode,
    LclConstant,
    LclFormattedValue,
    LclJoinedString,
    LclName,
    LclStringText,
)
from lclang.lang.printer._types import Render, RenderResult
from lclang.scopes import FRAME_PROXY

ATOM_PRECEDENCE = 100


def render_atom(node: LclAstNode, render: Render) -> RenderResult | None:
    """Render an atom or semantic interpolated string.

    :param node: Candidate AST node.
    :param render: Recursive dispatcher for formatted expressions.
    :returns: Canonical source and precedence, or ``None`` for another family.

    .. note::
       Constant rendering uses Python-compatible literal spellings only.
    """
    if isinstance(node, LclConstant):
        return internal_constant(node.value), ATOM_PRECEDENCE
    if isinstance(node, LclName):
        return str(node.identifier), ATOM_PRECEDENCE
    if isinstance(node, LclJoinedString):
        return f'f"{internal_joined(node, render)}"', ATOM_PRECEDENCE
    return None


def internal_constant(value: object) -> str:
    """Render a supported constant using its canonical literal spelling.

    :param value: Constant value to render.
    :returns: Python-compatible source text for the constant.
    :raises TypeError: If the value is not a supported LCL constant type.

    .. note::
       Boolean checks precede integer checks because ``bool`` is an ``int``
       subclass in Python.
    """
    if value is FRAME_PROXY:
        return "FRAME_PROXY"
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, (int, float, str, bytes)):
        return repr(value)
    raise TypeError(f"unsupported constant value: {type(value).__name__}")


def internal_joined(node: LclJoinedString, render: Render) -> str:
    """Render the parts of a semantic formatted string.

    :param node: Joined-string node whose values are rendered in order.
    :param render: Recursive dispatcher for expressions inside replacement
       fields.
    :returns: The joined f-string body without its surrounding quotes.
    :raises TypeError: If the node contains an unsupported value node.

    .. note::
       Replacement-field format specifications are rendered recursively so
       nested formatted strings retain their canonical spelling.
    """
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, LclStringText):
            parts.append(internal_ftext(value.text))
        elif isinstance(value, LclFormattedValue):
            field = render(value.expression, 0)
            if value.debug:
                field += "="
            if value.conversion is not None:
                field += f"!{value.conversion}"
            if value.format_spec is not None:
                field += f":{internal_joined(value.format_spec, render)}"
            parts.append(f"{{{field}}}")
        else:
            raise TypeError("joined string contains an unsupported value")
    return "".join(parts)


def internal_ftext(value: str) -> str:
    """Escape literal text for inclusion in a canonical f-string body.

    :param value: Literal text from a semantic joined string.
    :returns: Text with backslashes, quotes, braces, and control characters
       escaped for the printer's double-quoted f-string form.
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("{", "{{")
        .replace("}", "}}")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
