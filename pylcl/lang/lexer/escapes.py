"""Escape decoding for text, raw-text, and bytes literals."""

from __future__ import annotations

import unicodedata

_SIMPLE_ESCAPES = {
    "\\": "\\",
    "'": "'",
    '"': '"',
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}


class EscapeDecodeError(ValueError):
    """Report invalid literal content at a content-relative boundary.

    .. note::
       The lexer translates the relative boundary into an absolute source span.
    """

    def __init__(self, message: str, end: int) -> None:
        """Store a stable message and exclusive error boundary.

        :param message: Human-readable description of the invalid content.
        :param end: Content-relative exclusive offset for the diagnostic.
        :returns: ``None``.

        .. note::
           The offset is relative to the literal content rather than the
           complete source document.
        """
        super().__init__(message)
        self.message = message
        self.end = end


def decode_content(content: str, *, raw: bool, bytes_mode: bool) -> str | bytes:
    """Decode content between already-matched quote delimiters.

    :param content: Exact source content without its quote delimiters.
    :param raw: Preserve backslashes instead of decoding escapes when true.
    :param bytes_mode: Produce bytes and enforce ASCII source when true.
    :returns: Decoded text or bytes according to *bytes_mode*.
    :raises EscapeDecodeError: If an escape or bytes character is invalid.

    .. note::
       Quote termination and prefix validation are handled by ``literals.py``.
    """
    if bytes_mode and any(ord(character) > 127 for character in content):
        raise EscapeDecodeError(
            "non-ASCII source character in bytes literal",
            len(content),
        )
    if raw:
        return _encode_bytes(content) if bytes_mode else content
    decoded: list[str] = []
    cursor = 0
    while cursor < len(content):
        character = content[cursor]
        if character != "\\":
            decoded.append(character)
            cursor += 1
            continue
        value, cursor = _decode_escape(content, cursor + 1, bytes_mode=bytes_mode)
        decoded.append(value)
    joined = "".join(decoded)
    return _encode_bytes(joined) if bytes_mode else joined


def _decode_escape(content: str, cursor: int, *, bytes_mode: bool) -> tuple[str, int]:
    """Decode one escape beginning at a content-relative marker.

    :param content: Complete literal content being decoded.
    :param cursor: Content-relative offset of the escape marker.
    :param bytes_mode: Reject Unicode-only escapes when true.
    :returns: Decoded character and the next unread content offset.
    :raises EscapeDecodeError: If the escape syntax or value is invalid.

    .. note::
       The caller has already consumed the backslash and supplies the marker
       offset, so an empty or out-of-range offset is an internal misuse.
    """
    marker = content[cursor]
    if marker in _SIMPLE_ESCAPES:
        return _SIMPLE_ESCAPES[marker], cursor + 1
    if marker in "\r\n":
        is_crlf = marker == "\r" and _peek(content, cursor + 1) == "\n"
        return "", cursor + (2 if is_crlf else 1)
    if marker in "01234567":
        end = cursor + 1
        while end < min(cursor + 3, len(content)) and content[end] in "01234567":
            end += 1
        return chr(int(content[cursor:end], 8)), end
    if marker == "x":
        return _fixed_escape(content, cursor, 2)
    if marker in {"u", "U"}:
        if bytes_mode:
            raise EscapeDecodeError("Unicode escape in bytes literal", cursor + 1)
        return _fixed_escape(content, cursor, 4 if marker == "u" else 8)
    if marker == "N":
        if bytes_mode:
            raise EscapeDecodeError("named Unicode escape in bytes literal", cursor + 1)
        return _named_escape(content, cursor)
    raise EscapeDecodeError(f"unsupported escape \\{marker}", cursor + 1)


def _fixed_escape(content: str, marker_at: int, width: int) -> tuple[str, int]:
    """Decode a fixed-width hexadecimal escape.

    :param content: Complete literal content containing the escape.
    :param marker_at: Content-relative offset of ``x``, ``u``, or ``U``.
    :param width: Number of hexadecimal digits required after the marker.
    :returns: Decoded character and the next unread content offset.
    :raises EscapeDecodeError: If digits are missing, malformed, or out of range.

    .. note::
       The returned boundary includes the marker and exactly ``width`` digits,
       even when validation fails at the end of the available content.
    """
    end = marker_at + width + 1
    digits = content[marker_at + 1 : end]
    invalid_digit = any(
        character not in "0123456789abcdefABCDEF" for character in digits
    )
    if len(digits) != width or invalid_digit:
        raise EscapeDecodeError("invalid hexadecimal escape", end)
    try:
        return chr(int(digits, 16)), end
    except ValueError as error:
        raise EscapeDecodeError("invalid Unicode code point", end) from error


def _named_escape(content: str, marker_at: int) -> tuple[str, int]:
    """Decode a braced Unicode character-name escape.

    :param content: Complete literal content containing the escape.
    :param marker_at: Content-relative offset of the ``N`` marker.
    :returns: Named character and the next unread content offset.
    :raises EscapeDecodeError: If braces are missing or the name is unknown.

    .. note::
       Name resolution delegates to :mod:`unicodedata` and therefore follows
       the Unicode database bundled with the running Python version.
    """
    if _peek(content, marker_at + 1) != "{":
        raise EscapeDecodeError("invalid named Unicode escape", marker_at + 1)
    end = content.find("}", marker_at + 2)
    if end < 0:
        raise EscapeDecodeError("unterminated named Unicode escape", len(content))
    try:
        return unicodedata.lookup(content[marker_at + 2 : end]), end + 1
    except KeyError as error:
        raise EscapeDecodeError("unknown Unicode character name", end + 1) from error


def _encode_bytes(value: str) -> bytes:
    """Encode decoded literal text using the byte-literal character set.

    :param value: Text expected to contain only Latin-1 characters.
    :returns: Latin-1 encoded bytes.
    :raises EscapeDecodeError: If *value* contains a non-byte character.

    .. note::
       Latin-1 is used deliberately so each accepted source character maps to
       exactly one byte without replacement or normalization.
    """
    try:
        return value.encode("latin-1")
    except UnicodeEncodeError as error:
        raise EscapeDecodeError("non-byte character in bytes literal", error.end) from error


def _peek(text: str, offset: int) -> str:
    """Read one character or return an empty sentinel at the boundary.

    :param text: Content being inspected.
    :param offset: Candidate zero-based character offset.
    :returns: Character at *offset*, or ``""`` when it is past the end.

    .. note::
       The sentinel lets escape recognizers inspect optional delimiters
       without raising ``IndexError``.
    """
    return text[offset] if offset < len(text) else ""
