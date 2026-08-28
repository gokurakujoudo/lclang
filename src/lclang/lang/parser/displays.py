"""Delimiter-specific parsing for collection displays and grouping."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from lclang.ast import (
    LclAstNode,
    LclDict,
    LclDictUnpack,
    LclKeyValue,
    LclList,
    LclSet,
    LclStarred,
    LclTuple,
)
from lclang.ast.displays import LclDictEntry
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind
from lclang.lang.parser.comprehensions import ComprehensionKind, parse_comprehension
from lclang.lang.parser.records import parse_record
from lclang.lang.parser.stream import TokenStream
from lclang.source import SourceSpan


class InternalDisplayParser:
    """Parse grouped, sequence, set, and dictionary displays.

    .. note::
       The opening token selects the display family, while nested-expression
       callbacks preserve the enclosing parser's precedence rules.
    """

    def __init__(
        self,
        stream: TokenStream,
        parse_nested: Callable[[], LclAstNode],
        parse_nonconditional: Callable[[], LclAstNode],
    ) -> None:
        """Bind parser callbacks and consume the display opening token.

        :param stream: Token stream positioned at an opening delimiter.
        :param parse_nested: Callback parsing one nested expression.
        :param parse_nonconditional: Callback parsing comprehension clauses.
        :returns: ``None``.

        .. note::
           The consumed opening token is retained so every resulting node can
           receive a span covering its complete display.
        """
        self.stream = stream
        self.parse_nested = parse_nested
        self.parse_nonconditional = parse_nonconditional
        self.opening = stream.advance()

    def parse(self) -> LclAstNode:
        """Dispatch parsing according to the opening delimiter.

        :returns: Grouped expression or collection-display AST node.

        .. note::
           Parentheses, brackets, and braces are dispatched separately because
           they permit different unpacking and comprehension forms.
        """
        if self.opening.kind is TokenKind.LPAREN:
            return self.internal_parenthesized()
        if self.opening.kind is TokenKind.LBRACKET:
            return self.internal_list()
        return self.internal_braces()

    def internal_parenthesized(self) -> LclAstNode:
        """Parse a parenthesized expression, tuple, or generator.

        :returns: Grouped expression, tuple, or generator-comprehension node.
        :raises LclSyntaxError: If a closing parenthesis or nested element is
           invalid.

        .. note::
           A single element without a comma remains grouped rather than
           becoming a one-element tuple.
        """
        if self.stream.current.kind is TokenKind.RPAREN:
            closing = self.stream.advance()
            return LclTuple((), span=self.internal_container_span(closing.span))
        first = self.internal_sequence_element()
        if self.stream.current.kind is TokenKind.KW_FOR:
            return self.internal_comprehension(first, ComprehensionKind.GENERATOR)
        if self.stream.match(TokenKind.COMMA) is None:
            closing = self.stream.expect(TokenKind.RPAREN, "expected closing parenthesis")
            return replace(first, span=self.internal_container_span(closing.span))
        elements = [first]
        while self.stream.peek().kind is not TokenKind.RPAREN:
            elements.append(self.internal_sequence_element())
            if self.stream.match(TokenKind.COMMA) is None:
                break
        closing = self.stream.expect(TokenKind.RPAREN, "expected closing tuple parenthesis")
        return LclTuple(tuple(elements), span=self.internal_container_span(closing.span))

    def internal_list(self) -> LclAstNode:
        """Parse a list display or list comprehension.

        :returns: List or list-comprehension AST node.
        :raises LclSyntaxError: If list delimiters, elements, or unpacking are
           invalid.

        .. note::
           A trailing comma is accepted, including after the final list
           element before the closing bracket.
        """
        if self.stream.current.kind is TokenKind.RBRACKET:
            closing = self.stream.advance()
            return LclList((), span=self.internal_container_span(closing.span))
        first = self.internal_sequence_element()
        if self.stream.current.kind is TokenKind.KW_FOR:
            return self.internal_comprehension(first, ComprehensionKind.LIST)
        elements = [first]
        while self.stream.match(TokenKind.COMMA) is not None:
            if self.stream.peek().kind is TokenKind.RBRACKET:
                break
            elements.append(self.internal_sequence_element())
        closing = self.stream.expect(TokenKind.RBRACKET, "expected closing list bracket")
        return LclList(tuple(elements), span=self.internal_container_span(closing.span))

    def internal_sequence_element(self) -> LclAstNode:
        """Parse one sequence element with optional iterable unpacking.

        :returns: Nested expression or starred sequence-element node.
        :raises LclSyntaxError: If mapping unpacking appears in a sequence.

        .. note::
           The star marker is retained in the AST so evaluation can expand the
           value at the collection boundary.
        """
        marker = self.stream.match(TokenKind.STAR)
        if marker is None:
            if self.stream.current.kind is TokenKind.DOUBLE_STAR:
                raise LclSyntaxError(
                    "mapping unpack is invalid in a sequence",
                    span=self.stream.current.span,
                )
            return self.parse_nested()
        value = self.parse_nested()
        return LclStarred(value, span=internal_merge_span(marker.span, value.span))

    def internal_braces(self) -> LclAstNode:
        """Parse a dictionary, set, or corresponding comprehension.

        :returns: Dictionary, set, or comprehension AST node.

        .. note::
           A colon after the first element selects dictionary syntax; otherwise
           the same brace-delimited form represents a set.
        """
        entry: LclDictEntry
        if self.stream.current.kind is TokenKind.RBRACE:
            closing = self.stream.advance()
            return LclDict((), span=self.internal_container_span(closing.span))
        if self.stream.current.kind is TokenKind.DOUBLE_STAR:
            marker = self.stream.advance()
            value = self.parse_nested()
            entry = LclDictUnpack(value, span=internal_merge_span(marker.span, value.span))
            if self.stream.peek().kind is TokenKind.KW_FOR:
                return self.internal_comprehension(entry, ComprehensionKind.DICT)
            return self.internal_dict([entry])
        if (
            self.stream.current.kind is TokenKind.IDENTIFIER
            and self.stream.peek(1).kind is TokenKind.EQUAL
        ):
            return parse_record(self.stream, self.opening.span, self.parse_nested)
        first = self.internal_sequence_element()
        if self.stream.match(TokenKind.COLON) is not None:
            value = self.parse_nested()
            entry = LclKeyValue(first, value, span=internal_merge_span(first.span, value.span))
            if self.stream.current.kind is TokenKind.KW_FOR:
                return self.internal_comprehension(entry, ComprehensionKind.DICT)
            return self.internal_dict([entry])
        if self.stream.current.kind is TokenKind.KW_FOR:
            return self.internal_comprehension(first, ComprehensionKind.SET)
        return self.internal_set([first])

    def internal_dict(self, entries: list[LclDictEntry]) -> LclDict:
        """Complete a dictionary from its already-parsed first entries.

        :param entries: Mutable entries collected before the remaining comma
           separated dictionary items are parsed.
        :returns: Immutable dictionary AST node.
        :raises LclSyntaxError: If dictionary delimiters, keys, values, or
           unpacking are invalid.

        .. note::
           Mapping unpack entries are preserved in source order alongside
           ordinary key-value entries.
        """
        while True:
            if entries and self.stream.match(TokenKind.COMMA) is None:
                break
            if self.stream.current.kind is TokenKind.RBRACE:
                break
            marker = self.stream.match(TokenKind.DOUBLE_STAR)
            if marker is not None:
                value = self.parse_nested()
                entries.append(
                    LclDictUnpack(value, span=internal_merge_span(marker.span, value.span))
                )
                continue
            if self.stream.current.kind is TokenKind.STAR:
                raise LclSyntaxError(
                    "iterable unpack is invalid in a dict",
                    span=self.stream.current.span,
                )
            key = self.parse_nested()
            self.stream.expect(TokenKind.COLON, "expected colon after dictionary key")
            value = self.parse_nested()
            entries.append(LclKeyValue(key, value, span=internal_merge_span(key.span, value.span)))
        closing = self.stream.expect(TokenKind.RBRACE, "expected closing dictionary brace")
        return LclDict(tuple(entries), span=self.internal_container_span(closing.span))

    def internal_set(self, elements: list[LclAstNode]) -> LclSet:
        """Complete a set from its already-parsed first elements.

        :param elements: Mutable elements collected before later comma
           separated values are parsed.
        :returns: Immutable set AST node.
        :raises LclSyntaxError: If set elements use mapping unpacking or mix
           set and dictionary entry syntax.

        .. note::
           The parser rejects a colon after an element instead of silently
           changing an already-selected set into a dictionary.
        """
        while self.stream.match(TokenKind.COMMA) is not None:
            if self.stream.current.kind is TokenKind.RBRACE:
                break
            if self.stream.current.kind is TokenKind.DOUBLE_STAR:
                raise LclSyntaxError(
                    "mapping unpack is invalid in a set",
                    span=self.stream.current.span,
                )
            element = self.internal_sequence_element()
            if self.stream.current.kind is TokenKind.COLON:
                raise LclSyntaxError(
                    "cannot mix set and dictionary entries",
                    span=self.stream.current.span,
                )
            elements.append(element)
        closing = self.stream.expect(TokenKind.RBRACE, "expected closing set brace")
        return LclSet(tuple(elements), span=self.internal_container_span(closing.span))

    def internal_container_span(self, closing: SourceSpan) -> SourceSpan:
        """Build a span from this display's opening through its closing token.

        :param closing: Span of the consumed closing delimiter.
        :returns: Half-open source span covering the complete display.

        .. note::
           The opening span is shared by all display-family parsers so source
           diagnostics cover the same complete construct.
        """
        return internal_merge_span(self.opening.span, closing)

    def internal_comprehension(
        self,
        head: LclAstNode,
        kind: ComprehensionKind,
    ) -> LclAstNode:
        """Parse comprehension clauses after an already-parsed head.

        :param head: Sequence element or dictionary entry before the first
           ``for`` clause.
        :param kind: Comprehension family selected by the opening delimiter.
        :returns: Complete generator or collection-comprehension AST node.
        :raises LclSyntaxError: If comprehension clauses or their closing
           delimiter are invalid.

        .. note::
           Clause parsing is delegated so all comprehension families share the
           same target, iterable, and filter validation.
        """
        return parse_comprehension(
            self.stream,
            head,
            kind,
            self.opening.span,
            self.parse_nonconditional,
        )


def parse_display(
    stream: TokenStream,
    parse_nested: Callable[[], LclAstNode],
    parse_nonconditional: Callable[[], LclAstNode],
) -> LclAstNode:
    """Parse one parenthesized or collection display.

    :param stream: Token stream positioned at ``(``, ``[``, or ``{``.
    :param parse_nested: Callback parsing one nested expression.
    :param parse_nonconditional: Callback parsing clause iterables and filters.
    :returns: Grouped expression or explicit collection-display node.
    :raises LclSyntaxError: If delimiters, entries, or unpacking are invalid.

    .. note::
       Comprehension clauses are parsed after display boundaries are identified.
    """
    return InternalDisplayParser(stream, parse_nested, parse_nonconditional).parse()


def internal_merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the boundary spans of one display expression.

    :param first: Span at the start of the display or entry.
    :param last: Span at its final consumed expression or delimiter.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The source origin is inherited from *first*, and intervening delimiters
       or entries are included in the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
