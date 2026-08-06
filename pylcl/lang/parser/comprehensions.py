"""Clause parsing and semantic node selection for comprehensions."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pylcl.ast import (
    LclAstNode,
    LclComprehensionClause,
    LclDictComprehension,
    LclDictUnpack,
    LclGenerator,
    LclKeyValue,
    LclListComprehension,
    LclName,
    LclSetComprehension,
)
from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind
from pylcl.lang.parser.stream import TokenStream
from pylcl.source import SourceSpan
from pylcl.types import VarName


class ComprehensionKind(StrEnum):
    """Select the semantic node and required closing delimiter.

    .. note::
       Values are internal diagnostic labels rather than language spellings.
    """

    GENERATOR = "generator"
    LIST = "list"
    SET = "set"
    DICT = "dict"


_CLOSING = {
    ComprehensionKind.GENERATOR: TokenKind.RPAREN,
    ComprehensionKind.LIST: TokenKind.RBRACKET,
    ComprehensionKind.SET: TokenKind.RBRACE,
    ComprehensionKind.DICT: TokenKind.RBRACE,
}


def parse_comprehension(
    stream: TokenStream,
    head: LclAstNode,
    kind: ComprehensionKind,
    opening: SourceSpan,
    parse_nonconditional: Callable[[], LclAstNode],
) -> LclAstNode:
    """Parse clauses following an already-parsed comprehension head.

    :param stream: Token stream positioned at the first ``for``.
    :param head: Sequence element or explicit dictionary entry.
    :param kind: Semantic collection form and closing delimiter.
    :param opening: Opening-delimiter span used for the complete node.
    :param parse_nonconditional: Callback parsing iterable and filter values.
    :returns: Complete generator or collection-comprehension node.
    :raises LclSyntaxError: If clauses, target, head, or closing syntax is invalid.

    .. note::
       At least one clause is guaranteed because the first ``for`` is required.
    """
    clauses: list[LclComprehensionClause] = []
    while (for_token := stream.match(TokenKind.KW_FOR)) is not None:
        target_token = stream.expect(TokenKind.IDENTIFIER, "expected comprehension target name")
        target = LclName(VarName(target_token.lexeme), span=target_token.span)
        stream.expect(TokenKind.KW_IN, "comprehension target requires in")
        iterable = parse_nonconditional()
        conditions: list[LclAstNode] = []
        while stream.match(TokenKind.KW_IF) is not None:
            conditions.append(parse_nonconditional())
        final = conditions[-1] if conditions else iterable
        clauses.append(
            LclComprehensionClause(
                target,
                iterable,
                tuple(conditions),
                span=_merge_span(for_token.span, final.span),
            )
        )
    closing = stream.expect(_CLOSING[kind], "expected closing comprehension delimiter")
    span = _merge_span(opening, closing.span)
    clause_tuple = tuple(clauses)
    if kind is ComprehensionKind.GENERATOR:
        return LclGenerator(head, clause_tuple, span=span)
    if kind is ComprehensionKind.LIST:
        return LclListComprehension(head, clause_tuple, span=span)
    if kind is ComprehensionKind.SET:
        return LclSetComprehension(head, clause_tuple, span=span)
    if not isinstance(head, (LclKeyValue, LclDictUnpack)):
        raise LclSyntaxError("invalid dictionary comprehension head", span=head.span)
    return LclDictComprehension(head, clause_tuple, span=span)


def _merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the opening and final spans of one comprehension construct.

    :param first: Span at the beginning of the parsed construct.
    :param last: Span at its final consumed token.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The origin comes from *first*; the range intentionally includes all
       source text between the two boundary spans.
    """
    return SourceSpan(first.origin, first.start, last.end)
