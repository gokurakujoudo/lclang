"""Single-owner token cursor and parser-level token diagnostics."""

from __future__ import annotations

from lclang.error import LclSyntaxError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.language import Code as language_codes
from lclang.lang.lexer import Token, TokenKind


@guard_constructor(LclValidationError, language_codes.NATIVE_121)
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
                code=language_codes.E21_TOKEN_STREAM_REQUIRES_A_FINAL_EOF_TOKEN,
            )
        self.internal_index = 0

    @property
    @guard_failure(LclSyntaxError, language_codes.NATIVE_121)
    def current(self) -> Token:
        """Return the unconsumed lookahead token.

        :returns: Current token or the stable EOF sentinel.

        .. note::
           Reading lookahead never advances the stream.
        """
        return self._tokens[self.internal_index]

    @guard_failure(LclSyntaxError, language_codes.NATIVE_121)
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

    @guard_failure(LclSyntaxError, language_codes.NATIVE_121)
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
                code=language_codes.E21_TOKEN_LOOKAHEAD_OFFSET_CANNOT_BE_NEGATIVE,
            )
        index = min(self.internal_index + offset, len(self._tokens) - 1)
        return self._tokens[index]

    @guard_failure(LclSyntaxError, language_codes.NATIVE_121)
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

    @guard_failure(LclSyntaxError, language_codes.NATIVE_121)
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
                code = language_codes.EXPECTED_NAME
            elif kind in {TokenKind.RPAREN, TokenKind.RBRACKET, TokenKind.RBRACE}:
                code = language_codes.EXPECTED_CLOSER
            elif kind.name.startswith("KW_"):
                code = language_codes.EXPECTED_KEYWORD
            else:
                code = language_codes.EXPECTED_SEPARATOR
            raise LclSyntaxError(message, span=self.current.span, code=code)
        return token
