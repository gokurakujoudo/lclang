"""Single-owner token cursor and parser-level token diagnostics.

Defines ``TokenStream``.
"""

from __future__ import annotations

from lclang.error import LanguageErrorCode, LclSyntaxError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.engine.lexer import Token, TokenKind


@guard_constructor(LclValidationError, LanguageErrorCode.E21_EXPRESSION_PARSING_NATIVE_FAILURE)
class TokenStream:
    """Provide stable lookahead over one EOF-terminated token sequence.

    :param tokens: Source-order tokens containing a final EOF sentinel.
    :raises LclValidationError: If no EOF token remains after newline normalization.

    .. note::
       Physical newline tokens are removed; EOF advancement is idempotent.
    """

    def __init__(self, tokens: list[Token]) -> None:
        """Normalize newlines and validate the sentinel.

        :param tokens: Source-order lexer output.
        :returns: ``None``.
        :raises LclValidationError: If *tokens* has no final EOF token.

        .. note::
           The stream keeps immutable token objects but owns its cursor index.
        """
        self._tokens = tuple(token for token in tokens if token.kind is not TokenKind.NEWLINE)
        if not self._tokens or self._tokens[-1].kind is not TokenKind.EOF:
            raise LclValidationError(
                "token stream requires a final EOF token",
                code=LanguageErrorCode.E21_TOKEN_STREAM_REQUIRES_A_FINAL_EOF_TOKEN,
            )
        self.internal_index = 0

    @property
    @guard_failure(LclSyntaxError, LanguageErrorCode.E21_EXPRESSION_PARSING_NATIVE_FAILURE)
    def current(self) -> Token:
        """Return the unconsumed lookahead token.

        :returns: Current token or the stable EOF sentinel.

        .. note::
           Reading lookahead never advances the stream.
        """
        return self._tokens[self.internal_index]

    @guard_failure(LclSyntaxError, LanguageErrorCode.E21_EXPRESSION_PARSING_NATIVE_FAILURE)
    def advance(self) -> Token:
        """Consume and return the current token.

        :returns: Token current before this call.

        .. note::
           Consuming EOF leaves the cursor on that same sentinel.
        """
        token = self.current
        if token.kind is not TokenKind.EOF:
            self.internal_index += 1
        return token

    @guard_failure(LclSyntaxError, LanguageErrorCode.E21_EXPRESSION_PARSING_NATIVE_FAILURE)
    def peek(self, offset: int = 0) -> Token:
        """Return bounded lookahead without consuming a token.

        :param offset: Non-negative distance from current lookahead.
        :returns: Requested token or the EOF sentinel beyond available input.
        :raises LclValidationError: If *offset* is negative.

        .. note::
           Arbitrarily large offsets are safe and resolve to EOF.
        """
        if offset < 0:
            raise LclValidationError(
                "token lookahead offset cannot be negative",
                code=LanguageErrorCode.E21_TOKEN_LOOKAHEAD_OFFSET_CANNOT_BE_NEGATIVE,
            )
        index = min(self.internal_index + offset, len(self._tokens) - 1)
        return self._tokens[index]

    @guard_failure(LclSyntaxError, LanguageErrorCode.E21_EXPRESSION_PARSING_NATIVE_FAILURE)
    def match(self, *kinds: TokenKind) -> Token | None:
        """Consume the current token when its kind is requested.

        :param kinds: Accepted token kinds.
        :returns: Consumed token on a match, otherwise ``None``.

        .. note::
           A mismatch leaves the cursor unchanged.
        """
        if self.current.kind not in kinds:
            return None
        return self.advance()

    @guard_failure(LclSyntaxError, LanguageErrorCode.E21_EXPRESSION_PARSING_NATIVE_FAILURE)
    def expect(self, kind: TokenKind, message: str) -> Token:
        """Consume one required token or raise a syntax diagnostic.

        :param kind: Required token kind.
        :param message: Human-readable failure message.
        :returns: The consumed matching token.
        :raises LclSyntaxError: If current lookahead has another kind.

        .. note::
           Failure points at lookahead and does not consume it.
        """
        token = self.match(kind)
        if token is None:
            if kind is TokenKind.IDENTIFIER:
                code = LanguageErrorCode.E21_EXPECTED_NAME
            elif kind in {TokenKind.RPAREN, TokenKind.RBRACKET, TokenKind.RBRACE}:
                code = LanguageErrorCode.E21_EXPECTED_CLOSER
            elif kind.name.startswith("KW_"):
                code = LanguageErrorCode.E21_EXPECTED_KEYWORD
            else:
                code = LanguageErrorCode.E21_EXPECTED_SEPARATOR
            raise LclSyntaxError(message, span=self.current.span, code=code)
        return token
