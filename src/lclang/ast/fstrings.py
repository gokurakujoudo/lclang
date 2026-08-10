"""Semantic AST nodes for interpolated strings."""

from __future__ import annotations

from dataclasses import dataclass

from lclang.ast.base import LclAstNode


@dataclass(frozen=True, slots=True)
class LclStringText(LclAstNode):
    """Represent one non-empty text segment in a joined string.

    :param text: Decoded non-empty literal text.
    :param span: Optional source span inherited from :class:`LclAstNode`.
    :raises ValueError: If *text* is empty.

    .. note::
       Adjacent text is normalized by the parser before this node is created.
    """

    text: str

    def __post_init__(self) -> None:
        """Reject segments that add no semantic value.

        :raises ValueError: If the text is empty.
        """
        if not self.text:
            raise ValueError("f-string text segment cannot be empty")


@dataclass(frozen=True, slots=True)
class LclFormattedValue(LclAstNode):
    """Represent one evaluated replacement field.

    :param expression: Expression evaluated for the replacement field.
    :param conversion: Optional ``s``, ``r``, or ``a`` conversion.
    :param format_spec: Optional recursively joined format specification.
    :param debug: Whether the source used debug ``=`` syntax.
    :param span: Optional source span inherited from :class:`LclAstNode`.
    :raises ValueError: If *conversion* is outside the V1 conversion set.

    .. note::
       Conversion and formatting occur after expression evaluation.
    """

    expression: LclAstNode
    conversion: str | None = None
    format_spec: LclJoinedString | None = None
    debug: bool = False

    def __post_init__(self) -> None:
        """Validate the explicit V1 conversion vocabulary.

        :raises ValueError: If conversion is outside the supported set.
        """
        if self.conversion not in {None, "s", "r", "a"}:
            raise ValueError("unsupported f-string conversion")

    def children(self) -> tuple[LclAstNode, ...]:
        """Return expression followed by an optional format specification.

        :returns: One expression child and, when present, one format-spec child.

        .. note::
           Conversion and debug metadata are scalar values, not AST children.
        """
        if self.format_spec is None:
            return (self.expression,)
        return (self.expression, self.format_spec)


@dataclass(frozen=True, slots=True)
class LclJoinedString(LclAstNode):
    """Represent ordered semantic parts of an interpolated string.

    :param values: Text and formatted-value nodes in source order.
    :param span: Optional source span inherited from :class:`LclAstNode`.

    .. note::
       An empty joined string is valid and evaluates to an empty string.
    """

    values: tuple[LclAstNode, ...] = ()

    def children(self) -> tuple[LclAstNode, ...]:
        """Return joined-string values in source order.

        :returns: The immutable value tuple supplied at construction.

        .. note::
           Text and formatted values share the ordinary AST traversal protocol.
        """
        return self.values
