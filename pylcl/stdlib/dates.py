"""Locale-independent compact Gregorian date helpers."""

from datetime import date


def parse_ymd(ymd: str) -> date:
    """Parse one strict ASCII ``YYYYMMDD`` calendar date.

    :param ymd: Exactly eight ASCII decimal characters.
    :returns: Gregorian calendar date represented by *ymd*.
    :raises TypeError: If *ymd* is not a string.
    :raises ValueError: If syntax or calendar fields are invalid.

    .. note::
       Parsing is ASCII-, locale-, timezone-, and ambient-state-independent.
    """
    if not isinstance(ymd, str):
        raise TypeError("ymd must be a string")
    if len(ymd) != 8 or not ymd.isascii() or not ymd.isdigit():
        raise ValueError("ymd must contain exactly eight ASCII digits")
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))


def to_ymd(d: date) -> str:
    """Format one date as zero-padded ``YYYYMMDD`` text.

    :param d: Gregorian calendar date to format.
    :returns: Eight-character ASCII year-month-day text.
    :raises TypeError: If *d* is not a :class:`datetime.date` instance.

    .. note::
       Manual field formatting keeps years before 1000 four digits everywhere.
    """
    if not isinstance(d, date):
        raise TypeError("d must be a date")
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"
