"""Application-controlled task-local verbose logging.

Defines ``use_verbose``.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from lclang.error import LclValidationError, LoggerErrorCode
from lclang.error.verbose_context import ACTIVE_VERBOSE_LOGGER
from lclang.logger.logger import Logger


@contextmanager
def use_verbose(logger: logging.Logger | Logger | None, *, enabled: bool = True) -> Generator[None]:
    """Select a borrowed logger or explicitly silence tracing for this context.

    :param logger: Standard-library or lclang logger; None explicitly silences tracing.
    :param enabled: Boolean switch controlling the same application call site.
    :returns: Context manager restoring the prior destination on every exit.
    :raises LclValidationError: If enabled is not Boolean or logger has an unsupported type.

    .. note::
       Child tasks inherit this context. Callers own those tasks and must await
       them before closing an owned logger handler scope. This scope never
       changes handlers, levels, propagation or process logging ownership.
    """
    if not isinstance(enabled, bool):
        raise LclValidationError(
            "verbose enabled must be Boolean",
            code=LoggerErrorCode.E22_VERBOSE_ENABLED_MUST_BE_BOOLEAN,
        )
    if logger is not None and not isinstance(logger, (logging.Logger, Logger)):
        raise LclValidationError(
            "verbose logger must be a logging.Logger, Logger or None",
            code=LoggerErrorCode.E22_VERBOSE_LOGGER_TYPE,
        )
    token = ACTIVE_VERBOSE_LOGGER.set(logger if enabled else None)
    try:
        yield
    finally:
        ACTIVE_VERBOSE_LOGGER.reset(token)
