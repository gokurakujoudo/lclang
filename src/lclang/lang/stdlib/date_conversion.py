"""Locale-independent compact Gregorian date helpers.

Defines ``parse_ymd``, ``to_ymd``.
"""

from datetime import date

from lclang.error import LclStandardError, StandardLibraryErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_failure


@guard_failure(LclStandardError, StandardLibraryErrorCode.E41_DATE_CONVERSION_NATIVE_FAILURE)
def parse_ymd(ymd: str) -> date:
    """Parse one strict ASCII ``YYYYMMDD`` calendar date.

    :param ymd: Exactly eight ASCII decimal characters.
    :returns: Gregorian calendar date represented by *ymd*.
    :raises LclValidationError: If *ymd* is not a string.
    :raises LclValidationError: If syntax or calendar fields are invalid.

    .. note::
       Parsing is ASCII-, locale-, timezone-, and ambient-state-independent.
    """
    if not isinstance(ymd, str):
        raise LclValidationError(
            "ymd must be a string", code=StandardLibraryErrorCode.E41_YMD_MUST_BE_A_STRING
        )
    if len(ymd) != 8 or not ymd.isascii() or not ymd.isdigit():
        raise LclValidationError(
            "ymd must contain exactly eight ASCII digits",
            code=StandardLibraryErrorCode.E41_YMD_MUST_CONTAIN_EXACTLY_EIGHT_ASCII_DIGITS,
        )
    try:
        return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
    except ValueError as error:
        raise wrap_failure(
            error, LclValidationError, StandardLibraryErrorCode.E41_INVALID_DATE
        ) from error


@guard_failure(LclStandardError, StandardLibraryErrorCode.E41_DATE_CONVERSION_NATIVE_FAILURE)
def to_ymd(d: date) -> str:
    """Format one date as zero-padded ``YYYYMMDD`` text.

    :param d: Gregorian calendar date to format.
    :returns: Eight-character ASCII year-month-day text.
    :raises LclValidationError: If *d* is not a :class:`datetime.date` instance.

    .. note::
       Manual field formatting keeps years before 1000 four digits everywhere.
    """
    if not isinstance(d, date):
        raise LclValidationError(
            "d must be a date", code=StandardLibraryErrorCode.E41_INPUT_MUST_BE_A_DATE
        )
    return f"{d.year:04d}{d.month:02d}{d.day:02d}"
