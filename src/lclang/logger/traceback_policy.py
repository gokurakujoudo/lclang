"""Validation shared by logger declarations and external exception formatters.

Defines ``validate_traceback_style``.
"""

from typing import Literal

from lclang.error import LclValidationError, LoggerErrorCode


def validate_traceback_style(value: object) -> Literal["compact", "full"]:
    """Validate the human Python stack presentation policy.

    :param value: Untyped configuration or formatter input.
    :returns: Compact or full without coercion.
    :raises LclValidationError: If value is not text or is not a supported policy.
    """
    if not isinstance(value, str):
        raise LclValidationError(
            "logger.traceback_style: expected text",
            code=LoggerErrorCode.E11_LOGGER_TRACEBACK_STYLE_EXPECTED_TEXT,
        )
    if value == "compact":
        return "compact"
    if value == "full":
        return "full"
    raise LclValidationError(
        "logger.traceback_style: expected compact or full",
        code=LoggerErrorCode.E11_LOGGER_TRACEBACK_STYLE_EXPECTED_COMPACT_OR_FULL,
    )
