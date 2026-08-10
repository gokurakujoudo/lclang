"""Source-aware scanning for the core LCL token vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field

from lclang.errors import LclSyntaxError
from lclang.lang.lexer.literals import InternalLiteralScanError, scan_literal
from lclang.lang.lexer.tokens import Token, TokenKind
from lclang.source import SourceOrigin, SourcePosition, SourceSpan
from lclang.types import SourceName

_KEYWORDS = {kind.value: kind for kind in TokenKind if kind.name.startswith("KW_")}
_KEYWORDS.update(
    {
        "True": TokenKind.KW_TRUE,
        "False": TokenKind.KW_FALSE,
        "None": TokenKind.KW_NONE,
    }
)
_DOUBLE_TOKENS = {
    "**": TokenKind.DOUBLE_STAR,
    "//": TokenKind.DOUBLE_SLASH,
    "<<": TokenKind.LEFT_SHIFT,
    ">>": TokenKind.RIGHT_SHIFT,
    "<=": TokenKind.LESS_EQUAL,
    ">=": TokenKind.GREATER_EQUAL,
    "==": TokenKind.EQUAL_EQUAL,
    "!=": TokenKind.NOT_EQUAL,
    "?.": TokenKind.QUESTION_DOT,
    "??": TokenKind.DOUBLE_QUESTION,
    "->": TokenKind.ARROW,
}
_SINGLE_TOKENS = {
    kind.value: kind
    for kind in TokenKind
    if len(kind.value) == 1 and not kind.name.startswith("KW_")
}
_STRING_OR_NUMBER_START = frozenset("'\"")
# ASCII digits accepted at the start of numeric symbols.
_ASCII_DIGITS = frozenset("0123456789")


@dataclass(slots=True)
class InternalScanner:
    """Track mutable state while converting source text into tokens.

    :param text: Complete LCL source text.
    :param origin: Source origin attached to every emitted token.
    :param base_offset: Physical offset represented by local text offset zero.
    :param offset: Current zero-based source offset.
    :param line: Current one-based source line.
    :param column: Current one-based source column.
    :param tokens: Tokens emitted in source order.

    .. note::
       The scanner owns token accumulation and source position updates for one
       scan; it does not retain state between separate ``scan`` calls.
    """

    text: str
    origin: SourceOrigin
    base_offset: int = 0
    offset: int = 0
    line: int = 1
    column: int = 1
    tokens: list[Token] = field(default_factory=list)

    def scan(self) -> list[Token]:
        """Scan all remaining source characters and append an EOF token.

        :returns: Tokens in source order, including exactly one EOF token.
        :raises LclSyntaxError: If a literal or character sequence is invalid.

        .. note::
           The returned list is the scanner's owned accumulation and is not
           copied before being returned.
        """
        while self.offset < len(self.text):
            character = self.text[self.offset]
            try:
                literal = scan_literal(self.text, self.offset)
            except InternalLiteralScanError as error:
                start = self.internal_position()
                self.internal_advance_to(max(error.end, self.offset + 1))
                raise LclSyntaxError(error.message, span=self.internal_span(start)) from error
            if literal is not None:
                start = self.internal_position()
                self.internal_advance_to(literal.end)
                self.internal_emit(literal.kind, literal.lexeme, start, literal.value)
            elif character in " \t\f":
                self.internal_advance()
            elif character in "\r\n":
                self.internal_scan_newline()
            elif character == "#":
                self.internal_scan_comment()
            elif character.isidentifier():
                self.internal_scan_identifier()
            else:
                self.internal_scan_symbol(character)
        position = self.internal_position()
        self.tokens.append(Token(TokenKind.EOF, "", self.internal_span(position)))
        return self.tokens

    def internal_scan_identifier(self) -> None:
        """Consume an identifier and emit its keyword or identifier token.

        :returns: ``None``.

        .. note::
           An underscore is allowed after the first character through the
           same Unicode identifier rule used for continuation characters.
        """
        start = self.internal_position()
        start_offset = self.offset
        self.internal_advance()
        while self.offset < len(self.text):
            character = self.text[self.offset]
            if not f"_{character}".isidentifier():
                break
            self.internal_advance()
        lexeme = self.text[start_offset : self.offset]
        self.internal_emit(_KEYWORDS.get(lexeme, TokenKind.IDENTIFIER), lexeme, start)

    def internal_scan_symbol(self, character: str) -> None:
        """Consume one single- or double-character symbol token.

        :param character: Current source character at the scanner offset.
        :returns: ``None``.
        :raises LclSyntaxError: If the character is not a supported token.

        .. note::
           Double-character operators are checked before single-character
           symbols so the longest valid token wins.
        """
        start = self.internal_position()
        pair = self.text[self.offset : self.offset + 2]
        if pair in _DOUBLE_TOKENS:
            self.internal_advance()
            self.internal_advance()
            self.internal_emit(_DOUBLE_TOKENS[pair], pair, start)
            return
        if character in _SINGLE_TOKENS:
            self.internal_advance()
            self.internal_emit(_SINGLE_TOKENS[character], character, start)
            return
        self.internal_advance()
        is_literal = character in _ASCII_DIGITS or character in _STRING_OR_NUMBER_START
        category = "literal" if is_literal else "character"
        raise LclSyntaxError(
            f"unsupported {category} {character!r}",
            span=self.internal_span(start),
        )

    def internal_scan_comment(self) -> None:
        """Advance over a comment without emitting its text.

        :returns: ``None``.

        .. note::
           The terminating newline is left for :meth:`_scan_newline` so it
           still produces a source-aware NEWLINE token.
        """
        while self.offset < len(self.text) and self.text[self.offset] not in "\r\n":
            self.internal_advance()

    def internal_scan_newline(self) -> None:
        """Consume one newline sequence and emit a NEWLINE token.

        :returns: ``None``.

        .. note::
           CRLF advances by two code points but increments the logical line
           only once.
        """
        start = self.internal_position()
        start_offset = self.offset
        if self.text[self.offset : self.offset + 2] == "\r\n":
            self.offset += 2
        else:
            self.offset += 1
        self.line += 1
        self.column = 1
        self.internal_emit(TokenKind.NEWLINE, self.text[start_offset : self.offset], start)

    def internal_advance(self) -> None:
        """Advance one ordinary source code point and its column.

        :returns: ``None``.

        .. note::
           Newline sequences use :meth:`_advance_to` because they reset the
           column and increment the line instead.
        """
        self.offset += 1
        self.column += 1

    def internal_advance_to(self, end: int) -> None:
        """Advance to an absolute offset while tracking line boundaries.

        :param end: Exclusive target source offset.
        :returns: ``None``.

        .. note::
           Both CRLF and single-code-point newline forms reset the column to
           one and increment the logical line exactly once.
        """
        while self.offset < end:
            if self.text[self.offset : self.offset + 2] == "\r\n":
                self.offset += 2
                self.line += 1
                self.column = 1
            elif self.text[self.offset] in "\r\n":
                self.offset += 1
                self.line += 1
                self.column = 1
            else:
                self.internal_advance()

    def internal_position(self) -> SourcePosition:
        """Build the current source position from scanner state.

        :returns: Current one-based line/column and zero-based offset.

        .. note::
           Positions are snapshots, so later cursor movement does not mutate
           a position already attached to a token.
        """
        return SourcePosition(self.line, self.column, self.base_offset + self.offset)

    def internal_span(self, start: SourcePosition) -> SourceSpan:
        """Create a span from a saved start position to the current cursor.

        :param start: Position captured before consuming the token.
        :returns: Half-open source span ending at the current position.

        .. note::
           The scanner uses the same origin for every span in one source.
        """
        return SourceSpan(self.origin, start, self.internal_position())

    def internal_emit(
        self,
        kind: TokenKind,
        lexeme: str,
        start: SourcePosition,
        value: object | None = None,
    ) -> None:
        """Append one token covering the consumed source range.

        :param kind: Token classification to emit.
        :param lexeme: Exact source text consumed by the token.
        :param start: Position captured before token consumption.
        :param value: Optional decoded literal payload.
        :returns: ``None``.

        .. note::
           The token span is computed only when emission occurs, after the
           scanner has advanced to the token's exclusive end.
        """
        self.tokens.append(Token(kind, lexeme, self.internal_span(start), value))


def scan_tokens(
    text: str,
    *,
    origin: SourceOrigin | None = None,
    start: SourcePosition | None = None,
) -> list[Token]:
    """Scan source text into a source-aware token stream.

    :param text: Complete LCL source text.
    :param origin: Optional diagnostic origin; an in-memory origin is the default.
    :param start: Optional physical position of the first character.
    :returns: Tokens in source order ending with exactly one EOF token.
    :raises LclSyntaxError: If any character sequence is not valid LCL syntax.

    .. note::
       Offsets and columns count Unicode code points rather than encoded bytes.
    """
    selected_origin = origin or SourceOrigin(SourceName("<string>"))
    selected_start = start or SourcePosition(1, 1, 0)
    return InternalScanner(
        text,
        selected_origin,
        base_offset=selected_start.offset,
        line=selected_start.line,
        column=selected_start.column,
    ).scan()
