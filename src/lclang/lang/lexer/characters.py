"""Boundary-aware character reading for lexical recognizers."""

# Unitless ASCII digit characters come from the numeric literal grammar. A set
# rejects the empty boundary sentinel, unlike substring membership in a string.
ASCII_DIGITS = frozenset("0123456789")


def character_at(text: str, offset: int) -> str:
    """Read a character without crossing the end of the source.

    :param text: Source or literal content to inspect.
    :param offset: Nonnegative zero-based Unicode character offset.
    :returns: Character at the offset, or empty text at or beyond the end.
    """
    return text[offset] if offset < len(text) else ""
