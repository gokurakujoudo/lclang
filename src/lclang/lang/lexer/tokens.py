"""Immutable token kinds and source-aware token values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lclang.source import SourceSpan


class TokenKind(StrEnum):
    """Classify lexical values in the version-one LCL grammar.

    .. note::
       Enum values are diagnostic labels and exact fixed-token spellings.
    """

    IDENTIFIER = "identifier"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BYTES = "bytes"
    FSTRING = "f-string"
    KW_AND = "and"
    KW_OR = "or"
    KW_NOT = "not"
    KW_IF = "if"
    KW_ELSE = "else"
    KW_FOR = "for"
    KW_IN = "in"
    KW_IS = "is"
    KW_TRUE = "true"
    KW_FALSE = "false"
    KW_NONE = "none"
    KW_RAISE = "raise"
    KW_TRY = "try"
    KW_EXCEPT = "except"
    KW_FINALLY = "finally"
    KW_ASSERT = "assert"
    KW_WITH = "with"
    KW_AS = "as"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    COLON = ":"
    DOT = "."
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    DOUBLE_STAR = "**"
    SLASH = "/"
    DOUBLE_SLASH = "//"
    PERCENT = "%"
    AT = "@"
    LEFT_SHIFT = "<<"
    RIGHT_SHIFT = ">>"
    AMPERSAND = "&"
    PIPE = "|"
    CARET = "^"
    TILDE = "~"
    LESS = "<"
    LESS_EQUAL = "<="
    GREATER = ">"
    GREATER_EQUAL = ">="
    EQUAL_EQUAL = "=="
    NOT_EQUAL = "!="
    EQUAL = "="
    QUESTION_DOT = "?."
    DOUBLE_QUESTION = "??"
    ARROW = "->"  # Function signature separator.
    NEWLINE = "newline"
    EOF = "end of input"


@dataclass(frozen=True, slots=True)
class Token:
    """Represent an exact lexical slice and its source range.

    :param kind: Stable lexical classification.
    :param lexeme: Exact source text consumed for the token.
    :param span: Half-open source range of the lexeme.
    :param value: Decoded literal payload, otherwise `None`.

    .. note::
       Non-literal tokens always use ``None`` as their decoded value.
    """

    kind: TokenKind
    lexeme: str
    span: SourceSpan
    value: object | None = None
