"""Immutable lexical values produced by the f-string scanner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FStringText:
    """Represent one non-empty decoded text segment.

    :param text: Decoded literal text between replacement fields.

    .. note::
       The scanner omits empty text segments from the part sequence.
    """

    text: str


@dataclass(frozen=True, slots=True)
class FStringField:
    """Preserve one replacement expression and its lexical modifiers.

    :param expression: Stripped, non-empty LCL expression source.
    :param conversion: Optional ``s``, ``r``, or ``a`` conversion.
    :param format_spec: Optional recursive lexical format specification.
    :param debug: Whether the field used debug ``=`` syntax.

    .. note::
       Expression parsing occurs in the parser milestone, not in this value.
    """

    expression: str
    conversion: str | None = None
    format_spec: FStringValue | None = None
    debug: bool = False


@dataclass(frozen=True, slots=True)
class FStringValue:
    """Represent ordered lexical parts and raw-string mode.

    :param parts: Decoded text and replacement fields in source order.
    :param raw: Whether backslashes in text were preserved.

    .. note::
       A field-only or empty f-string legitimately has no text parts.
    """

    parts: tuple[FStringText | FStringField, ...]
    raw: bool


@dataclass(frozen=True, slots=True)
class FStringMatch:
    """Return an f-string value with its exclusive source boundary.

    :param value: Complete lexical value for the interpolated string.
    :param end: Exclusive code-point offset after the closing delimiter.

    .. note::
       Source origin and line information are attached by the outer scanner.
    """

    value: FStringValue
    end: int
