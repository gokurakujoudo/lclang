"""Brace-aware scanner for interpolated strings."""

from __future__ import annotations

from lclang.lang.lexer.characters import character_at
from lclang.lang.lexer.escapes import EscapeDecodeError, decode_content
from lclang.lang.lexer.fstring_values import (
    FStringField,
    FStringMatch,
    FStringText,
    FStringValue,
)


class FStringScanError(ValueError):
    """Report invalid interpolation at an absolute source boundary.

    .. note::
       The outer scanner converts this internal boundary into ``LclSyntaxError``.
    """

    def __init__(self, message: str, end: int) -> None:
        """Store a stable message and exclusive error boundary.

        :param message: Human-readable description of the malformed f-string.
        :param end: Absolute exclusive source offset for the diagnostic.
        :returns: ``None``.

        .. note::
           The outer lexer translates this boundary into the final source
           span reported to callers.
        """
        super().__init__(message)
        self.message = message
        self.end = end


class InternalFStringScanner:
    """Maintain cursor state while scanning one interpolated string.

    .. note::
       The scanner balances delimiters and fields but leaves embedded
       expression parsing to the ordinary LCL parser.
    """

    def __init__(self, text: str, quote_at: int, *, raw: bool) -> None:
        """Initialize delimiters and the cursor after the opening quote.

        :param text: Complete source text containing the f-string.
        :param quote_at: Offset of the first opening quote after the prefix.
        :param raw: Preserve backslashes in literal text when true.
        :returns: ``None``.

        .. note::
           Triple-quoted delimiters are detected before scanning any fields.
        """
        self.text = text
        self.raw = raw
        self.quote = text[quote_at]
        self.triple = text.startswith(self.quote * 3, quote_at)
        self.delimiter = self.quote * (3 if self.triple else 1)
        self.cursor = quote_at + len(self.delimiter)

    def scan(self) -> FStringMatch:
        """Scan the complete f-string and return its lexical value.

        :returns: Lexical f-string value and exclusive closing boundary.

        .. note::
           The scanner's cursor remains at the first source offset after the
           closing delimiter.
        """
        parts = self.internal_parts(top_level=True)
        return FStringMatch(FStringValue(tuple(parts), self.raw), self.cursor)

    def internal_parts(self, *, top_level: bool) -> list[FStringText | FStringField]:
        """Collect text and fields until the current delimiter closes.

        :param top_level: Treat the outer string delimiter as the terminator
           when true; otherwise stop at a field's closing brace.
        :returns: Ordered text and replacement-field parts.
        :raises FStringScanError: If delimiters, braces, or termination are invalid.

        .. note::
           Doubled braces are emitted as literal braces and do not open or
           close a replacement field.
        """
        parts: list[FStringText | FStringField] = []
        text: list[str] = []
        while self.cursor < len(self.text):
            if top_level and self.text.startswith(self.delimiter, self.cursor):
                self.internal_flush(text, parts)
                self.cursor += len(self.delimiter)
                return parts
            character = self.text[self.cursor]
            if not top_level and character == "}":
                self.internal_flush(text, parts)
                self.cursor += 1
                return parts
            if character in "\r\n" and top_level and not self.triple:
                raise FStringScanError("newline in single-quoted f-string", self.cursor + 1)
            if character == "\\":
                text.append(character)
                self.cursor += 1
                if self.cursor < len(self.text):
                    text.append(self.text[self.cursor])
                    self.cursor += 1
                continue
            if self.text.startswith("{{", self.cursor):
                text.append("{")
                self.cursor += 2
                continue
            if self.text.startswith("}}", self.cursor):
                text.append("}")
                self.cursor += 2
                continue
            if character == "{":
                self.internal_flush(text, parts)
                parts.append(self.internal_field())
                continue
            if character == "}":
                raise FStringScanError("unmatched closing brace in f-string", self.cursor + 1)
            text.append(character)
            self.cursor += 1
        message = "unterminated f-string" if top_level else "unterminated format specification"
        raise FStringScanError(message, len(self.text))

    def internal_field(self) -> FStringField:
        """Scan one replacement field from its opening brace.

        :returns: Parsed lexical field with optional conversion and format
           specification.
        :raises FStringScanError: If the expression, delimiter, or field end is invalid.

        .. note::
           Bracket nesting is balanced lexically so braces inside nested
           literals do not terminate the field prematurely.
        """
        self.cursor += 1
        start = self.cursor
        stack: list[str] = []
        debug = False
        while self.cursor < len(self.text):
            character = self.text[self.cursor]
            if character in "'\"":
                self.cursor = self.internal_skip_quoted(self.cursor)
                continue
            if character in "([{":
                stack.append({"(": ")", "[": "]", "{": "}"}[character])
                self.cursor += 1
                continue
            if stack and character == stack[-1]:
                stack.pop()
                self.cursor += 1
                continue
            if character in ")]" and (not stack or character != stack[-1]):
                raise FStringScanError("mismatched delimiter in f-string field", self.cursor + 1)
            is_not_equal = character == "!" and self.text[self.cursor : self.cursor + 2] == "!="
            if not stack and character in "!:}" and not is_not_equal:
                break
            if not stack and character == "=" and self.internal_is_debug_equal(start):
                debug = True
                break
            if character == "\\":
                raise FStringScanError("backslash in f-string expression", self.cursor + 1)
            if character == "#":
                raise FStringScanError("comment in f-string expression", self.cursor + 1)
            self.cursor += 1
        expression = self.text[start : self.cursor].strip()
        if not expression:
            raise FStringScanError("empty f-string expression", self.cursor + 1)
        if debug:
            self.cursor += 1
            self.internal_skip_space()
        conversion = self.internal_conversion()
        format_spec = None
        if self.internal_peek() == ":":
            self.cursor += 1
            format_spec = FStringValue(tuple(self.internal_parts(top_level=False)), self.raw)
        elif self.internal_peek() == "}":
            self.cursor += 1
        else:
            end = min(self.cursor + 1, len(self.text))
            raise FStringScanError("unterminated f-string field", end)
        return FStringField(expression, conversion, format_spec, debug)

    def internal_conversion(self) -> str | None:
        """Read an optional field conversion marker.

        :returns: One of ``s``, ``r``, or ``a``, or ``None`` when absent.
        :raises FStringScanError: If ``!`` is followed by an unsupported marker.

        .. note::
           Conversion parsing consumes only the marker; format-spec parsing is
           handled by :meth:`_field`.
        """
        if self.internal_peek() != "!":
            return None
        self.cursor += 1
        conversion = self.internal_peek()
        if conversion not in {"s", "r", "a"}:
            raise FStringScanError("invalid f-string conversion", self.cursor + 1)
        self.cursor += 1
        return conversion

    def internal_is_debug_equal(self, start: int) -> bool:
        """Determine whether the current equals sign uses debug syntax.

        :param start: Content-relative start of the field expression.
        :returns: ``True`` for a standalone debug ``=``, otherwise ``False``.

        .. note::
           Comparison operators such as ``!=`` and ``==`` are excluded from
           debug-field detection.
        """
        previous = self.text[self.cursor - 1] if self.cursor > start else ""
        following = self.text[self.cursor + 1 : self.cursor + 2]
        return previous not in "<>=!" and following != "="

    def internal_skip_quoted(self, start: int) -> int:
        """Advance past a quoted expression fragment.

        :param start: Offset of the opening quote in the source text.
        :returns: Offset immediately after the matching quote delimiter.
        :raises FStringScanError: If the quoted fragment is unterminated.

        .. note::
           Escaped characters advance by two source positions, while triple
           quotes use their full delimiter length.
        """
        quote = self.text[start]
        delimiter = quote * (3 if self.text.startswith(quote * 3, start) else 1)
        cursor = start + len(delimiter)
        while cursor < len(self.text):
            if self.text.startswith(delimiter, cursor):
                return cursor + len(delimiter)
            cursor += 2 if self.text[cursor] == "\\" else 1
        raise FStringScanError("unterminated quote in f-string expression", len(self.text))

    def internal_flush(
        self,
        text: list[str],
        parts: list[FStringText | FStringField],
    ) -> None:
        """Decode pending literal text and append it as one text part.

        :param text: Mutable source-character buffer to flush.
        :param parts: Mutable ordered part list receiving the decoded text.
        :returns: ``None``.
        :raises FStringScanError: If the buffered text contains an invalid escape.

        .. note::
           The source buffer is cleared after successful decoding so each
           literal run becomes exactly one lexical text part.
        """
        if not text:
            return
        source = "".join(text)
        try:
            decoded = decode_content(source, raw=self.raw, bytes_mode=False)
        except EscapeDecodeError as error:
            raise FStringScanError(error.message, self.cursor) from error
        parts.append(FStringText(str(decoded)))
        text.clear()

    def internal_skip_space(self) -> None:
        """Consume spaces allowed after a debug field equals sign.

        :returns: ``None``.

        .. note::
           Only spaces, tabs, and form feeds are skipped; newlines remain
           subject to the surrounding f-string rules.
        """
        while self.internal_peek() in {" ", "\t", "\f"}:
            self.cursor += 1

    def internal_peek(self) -> str:
        """Return the single source character at the current cursor.

        :returns: Current character, or ``""`` at end of source.

        .. note::
           The shared character reader supplies an empty sentinel without ``IndexError``
           at the input boundary.
        """
        return character_at(self.text, self.cursor)


def scan_fstring(text: str, quote_at: int, *, raw: bool) -> FStringMatch:
    """Scan one f-string whose opening quote begins at *quote_at*.

    :param text: Complete source text containing the f-string.
    :param quote_at: Offset of the first opening quote after the prefix.
    :param raw: Preserve backslashes in literal text when true.
    :returns: The lexical f-string value and exclusive closing boundary.
    :raises FStringScanError: If braces, fields, quotes, or modifiers are invalid.

    .. note::
       Embedded expression text is balanced but is not parsed as LCL here.
    """
    return InternalFStringScanner(text, quote_at, raw=raw).scan()
