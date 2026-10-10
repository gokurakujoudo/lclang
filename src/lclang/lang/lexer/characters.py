"""Boundary-aware character reading for lexical recognizers."""

from lclang.error import LclSyntaxError
from lclang.error.boundary import guard_failure
from lclang.error.codes.language import Code as language_codes

# Unitless ASCII digit characters come from the numeric literal grammar. A set
# rejects the empty boundary sentinel, unlike substring membership in a string.
ASCII_DIGITS = frozenset("0123456789")


@guard_failure(LclSyntaxError, language_codes.NATIVE_111)
def character_at(text: str, offset: int) -> str:
    """Read a character without crossing the end of the source.

    :param text: Source or literal content to inspect.
    :param offset: Nonnegative zero-based Unicode character offset.
    :returns: Character at the offset, or empty text at or beyond the end.
    """
    return text[offset] if offset < len(text) else ""
