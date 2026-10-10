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
from lclang.error import LclEvaluationError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.language import Code as language_codes
from lclang.lang.printer._types import Render, RenderResult
from lclang.override_markers import OverrideMarker
from lclang.scopes import FRAME_PROXY

# Unitless precedence 100 matches atomic expressions in the parser; the highest rank avoids
# unnecessary parentheses.
ATOM_PRECEDENCE = 100


@guard_failure(LclEvaluationError, language_codes.NATIVE_141)
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
    :raises LclValidationError: If the value is not a supported LCL constant type.

    .. note::
       Boolean checks precede integer checks because ``bool`` is an ``int``
       subclass in Python.
    """
    if value is FRAME_PROXY:
        return "FRAME_PROXY"
    if isinstance(value, OverrideMarker):
        return value.value
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, (int, float, str, bytes)):
        return repr(value)
    raise LclValidationError(
        f"unsupported constant value: {type(value).__name__}",
        code=language_codes.E41_UNSUPPORTED_CONSTANT_VALUE_VALUE,
    )


def internal_joined(node: LclJoinedString, render: Render) -> str:
    """Render the parts of a semantic formatted string.

    :param node: Joined-string node whose values are rendered in order.
    :param render: Recursive dispatcher for expressions inside replacement
       fields.
    :returns: The joined f-string body without its surrounding quotes.
    :raises LclValidationError: If the node contains an unsupported value node.

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
            raise LclValidationError(
                "joined string contains an unsupported value",
                code=language_codes.E41_JOINED_STRING_CONTAINS_AN_UNSUPPORTED_VALUE,
            )
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
