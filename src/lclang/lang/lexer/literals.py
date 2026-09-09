"""Matching and decoding for non-interpolated LCL literals."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lclang.lang.lexer.characters import ASCII_DIGITS, character_at
from lclang.lang.lexer.escapes import EscapeDecodeError, decode_content
from lclang.lang.lexer.fstrings import FStringScanError, scan_fstring
from lclang.lang.lexer.tokens import TokenKind

# Unitless regular expressions implement the numeric literal grammar; separate candidate and
# validation patterns retain precise malformed-literal errors.
_DIGITS = r"\d(?:_?\d)*"
_FLOAT = re.compile(
    rf"(?:(?:(?:{_DIGITS})?\.(?:{_DIGITS})?)(?:[eE][+-]?{_DIGITS})?"
    rf"|{_DIGITS}[eE][+-]?{_DIGITS})"
)
# Unitless regular expressions implement the numeric literal grammar; separate candidate and
# validation patterns retain precise malformed-literal errors.
_INTEGER = re.compile(
    r"(?:0[xX]_?[0-9a-fA-F](?:_?[0-9a-fA-F])*"
    r"|0[oO]_?[0-7](?:_?[0-7])*"
    r"|0[bB]_?[01](?:_?[01])*"
    r"|0(?:_?0)*|[1-9](?:_?\d)*)"
)
# Unitless regular expressions implement the numeric literal grammar; separate candidate and
# validation patterns retain precise malformed-literal errors.
_NUMBER_CANDIDATE = re.compile(r"(?:\d|\.\d)(?:[A-Za-z0-9_.]|(?<=[eE])[+-])*")
# ASCII digits accepted by Python-style numeric literals.


@dataclass(frozen=True, slots=True)
class LiteralMatch:
    """Describe one decoded literal and its exclusive source boundary.

    :param kind: Token classification for the decoded literal.
    :param lexeme: Exact source slice including prefix and quotes when present.
    :param value: Decoded runtime-neutral literal value.
    :param end: Exclusive code-point offset in the scanned source.

    .. note::
       The match has no origin; the scanner attaches the final source span.
    """

    kind: TokenKind
    lexeme: str
    value: object
    end: int


class InternalLiteralScanError(Exception):
    """Carry a literal error message and content-relative boundary.

    .. note::
       The public scanner adds the final source-aware diagnostic.
    """

    def __init__(self, message: str, end: int) -> None:
        """Store the malformed-literal details for the caller.

        :param message: Human-readable description of the malformed literal.
        :param end: Absolute exclusive source offset for the error.
        :returns: ``None``.

        .. note::
           The offset is already adjusted for escape-decoder failures.
        """
        super().__init__(message)
        self.message = message
        self.end = end


def scan_literal(text: str, start: int) -> LiteralMatch | None:
    """Match and decode the literal beginning at *start*.

    :param text: Complete source text containing the candidate.
    :param start: Zero-based candidate offset.
    :returns: A literal match, or ``None`` when another token begins at *start*.
    :raises InternalLiteralScanError: If a candidate literal is malformed.

    .. note::
       The caller must provide a code-point boundary inside *text*.
    """
    if start >= len(text):
        return None
    character = text[start]
    if character in ASCII_DIGITS or (
        character == "." and character_at(text, start + 1) in ASCII_DIGITS
    ):
        return internal_scan_number(text, start)
    prefix, quote_at = internal_string_prefix(text, start)
    if quote_at is None:
        return None
    if "f" in prefix.lower():
        try:
            match = scan_fstring(text, quote_at, raw="r" in prefix.lower())
        except FStringScanError as error:
            raise InternalLiteralScanError(error.message, error.end) from error
        return LiteralMatch(
            TokenKind.FSTRING,
            text[start : match.end],
            match.value,
            match.end,
        )
    return internal_scan_string(text, start, prefix, quote_at)


def internal_scan_number(text: str, start: int) -> LiteralMatch:
    """Match and decode a numeric literal candidate.

    :param text: Complete source text containing the candidate.
    :param start: Zero-based offset at the candidate's first character.
    :returns: Decoded integer or floating-point literal match.
    :raises AssertionError: If called without a numeric prefix.
    :raises InternalLiteralScanError: If the candidate is not valid numeric syntax.

    .. note::
       Underscores are removed only for conversion; the original lexeme is
       retained in the returned match.
    """
    candidate_match = _NUMBER_CANDIDATE.match(text, start)
    if candidate_match is None:  # pragma: no cover - guarded by scan_literal
        raise AssertionError("numeric scanner called without a numeric prefix")
    lexeme = candidate_match.group()
    clean = lexeme.replace("_", "")
    if _FLOAT.fullmatch(lexeme):
        return LiteralMatch(TokenKind.FLOAT, lexeme, float(clean), candidate_match.end())
    if _INTEGER.fullmatch(lexeme):
        base = 0 if clean.lower().startswith(("0x", "0o", "0b")) else 10
        return LiteralMatch(TokenKind.INTEGER, lexeme, int(clean, base), candidate_match.end())
    raise InternalLiteralScanError("invalid numeric literal", candidate_match.end())


def internal_string_prefix(text: str, start: int) -> tuple[str, int | None]:
    """Recognize an optional literal prefix and following quote.

    :param text: Complete source text containing the candidate.
    :param start: Zero-based offset at the possible prefix or quote.
    :returns: Prefix and quote offset, or ``("", None)`` when absent.

    .. note::
       Only grammar-supported prefix combinations are accepted.
    """
    if text[start] in "'\"":
        return "", start
    for length in (2, 1):
        prefix = text[start : start + length]
        quote_at = start + length
        quote = character_at(text, quote_at)
        valid_prefixes = {"b", "r", "f", "br", "rb", "fr", "rf"}
        if prefix.lower() in valid_prefixes and quote and quote in "'\"":
            return prefix, quote_at
    return "", None


def internal_scan_string(text: str, start: int, prefix: str, quote_at: int) -> LiteralMatch:
    """Match, decode, and classify one quoted literal.

    :param text: Complete source text containing the literal.
    :param start: Zero-based offset at the prefix or opening quote.
    :param prefix: Validated literal prefix, possibly empty.
    :param quote_at: Offset of the opening quote after *prefix*.
    :returns: Decoded string or bytes literal match.
    :raises InternalLiteralScanError: If the literal is unterminated or malformed.

    .. note::
       Triple-quoted literals may contain newlines; single-quoted literals may not.
    """
    quote = text[quote_at]
    triple = text.startswith(quote * 3, quote_at)
    delimiter = quote * (3 if triple else 1)
    content_start = quote_at + len(delimiter)
    cursor = content_start
    while cursor < len(text):
        if text.startswith(delimiter, cursor):
            end = cursor + len(delimiter)
            content = text[content_start:cursor]
            try:
                value = decode_content(
                    content,
                    raw="r" in prefix.lower(),
                    bytes_mode="b" in prefix.lower(),
                )
            except EscapeDecodeError as error:
                raise InternalLiteralScanError(error.message, content_start + error.end) from error
            kind = TokenKind.BYTES if "b" in prefix.lower() else TokenKind.STRING
            return LiteralMatch(kind, text[start:end], value, end)
        if text[cursor] in "\r\n" and not triple:
            raise InternalLiteralScanError("newline in single-quoted literal", cursor + 1)
        if text[cursor] == "\\":
            cursor += 1
            if (
                cursor < len(text)
                and text[cursor] == "\r"
                and character_at(text, cursor + 1) == "\n"
            ):
                cursor += 1
        cursor += 1
    raise InternalLiteralScanError("unterminated string literal", len(text))
