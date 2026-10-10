"""Handler-visible CLI invocation context.

Defines ``CliContext``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from lclang.cli.cli_models import CliParams
from lclang.error import CliErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.runtime import Frame
from lclang.logger import Logger


@guard_constructor(LclValidationError, CliErrorCode.E15_CLI_CONTEXT_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class CliContext:
    """Expose immutable invocation metadata and owned execution services.

    :param as_of_date: Effective invocation date.
    :param dryrun: Handler-controlled side-effect signal.
    :param frame: Top invocation Frame used for lazy lookup.
    :param logger: Isolated standard-library command logger.
    :param raw_params: Complete immutable parsed parameters.
    """

    as_of_date: date
    dryrun: bool
    frame: Frame
    logger: logging.Logger | Logger
    raw_params: CliParams

    @guard_failure(LclValidationError, CliErrorCode.E15_CLI_CONTEXT_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate references without taking over their lifecycle.

        :returns: ``None``.
        :raises LclValidationError: If a context field has the wrong public type.
        """
        if not isinstance(self.as_of_date, date):
            raise LclValidationError(
                "context as-of date must be a date",
                code=CliErrorCode.E15_CONTEXT_AS_OF_DATE_MUST_BE_A_DATE,
            )
        if not isinstance(self.dryrun, bool):
            raise LclValidationError(
                "context dryrun must be Boolean",
                code=CliErrorCode.E15_CONTEXT_DRYRUN_MUST_BE_BOOLEAN,
            )
        if not isinstance(self.frame, Frame):
            raise LclValidationError(
                "context frame must be a Frame", code=CliErrorCode.E15_CONTEXT_FRAME_MUST_BE_A_FRAME
            )
        if not isinstance(self.logger, (logging.Logger, Logger)):
            raise LclValidationError(
                "context logger must be a Logger",
                code=CliErrorCode.E15_CONTEXT_LOGGER_MUST_BE_A_LOGGER,
            )
        if not isinstance(self.raw_params, CliParams):
            raise LclValidationError(
                "context raw params must be CliParams",
                code=CliErrorCode.E15_CONTEXT_RAW_PARAMS_MUST_BE_CLIPARAMS,
            )
