"""Clause parsing and semantic node selection for comprehensions.

Defines ``ComprehensionKind``, ``parse_comprehension``.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from lclang.common.identifiers import VarName
from lclang.common.source_location import SourceSpan, merge_source_spans
from lclang.error import LanguageErrorCode, LclSyntaxError
from lclang.error.operation_guard import guard_failure
from lclang.lang.ast import (
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
from lclang.lang.engine.lexer import TokenKind
from lclang.lang.engine.parser.binding_validation import validate_binding_name
from lclang.lang.engine.parser.token_stream import TokenStream


class ComprehensionKind(StrEnum):
    """Select the semantic node and required closing delimiter.

    .. note::
       Values are internal diagnostic labels rather than language spellings.
    """

    # Unitless comprehension kinds and closing tokens follow display syntax; separate entries
    # select the result container and matching terminator.
    GENERATOR = "generator"
    LIST = "list"
    SET = "set"
    DICT = "dict"


# Unitless comprehension kinds and closing tokens follow display syntax; separate entries select
# the result container and matching terminator.
_CLOSING = {
    ComprehensionKind.GENERATOR: TokenKind.RPAREN,
    ComprehensionKind.LIST: TokenKind.RBRACKET,
    ComprehensionKind.SET: TokenKind.RBRACE,
    ComprehensionKind.DICT: TokenKind.RBRACE,
}


@guard_failure(LclSyntaxError, LanguageErrorCode.E27_COMPREHENSION_PARSING_NATIVE_FAILURE)
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
        validate_binding_name(target_token)
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
                span=merge_source_spans(for_token.span, final.span),
            )
        )
    closing = stream.expect(_CLOSING[kind], "expected closing comprehension delimiter")
    span = merge_source_spans(opening, closing.span)
    clause_tuple = tuple(clauses)
    if kind is ComprehensionKind.GENERATOR:
        return LclGenerator(head, clause_tuple, span=span)
    if kind is ComprehensionKind.LIST:
        return LclListComprehension(head, clause_tuple, span=span)
    if kind is ComprehensionKind.SET:
        return LclSetComprehension(head, clause_tuple, span=span)
    if not isinstance(head, (LclKeyValue, LclDictUnpack)):
        raise LclSyntaxError(
            "invalid dictionary comprehension head",
            span=head.span,
            code=LanguageErrorCode.E27_INVALID_DICTIONARY_COMPREHENSION_HEAD,
        )
    return LclDictComprehension(head, clause_tuple, span=span)
