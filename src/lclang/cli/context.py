"""Handler-visible CLI invocation context."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from lclang.cli.models import CliParams
from lclang.runtime import Frame


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
    logger: logging.Logger
    raw_params: CliParams

    def __post_init__(self) -> None:
        """Validate references without taking over their lifecycle.

        :returns: ``None``.
        :raises TypeError: If a context field has the wrong public type.
        """
        if not isinstance(self.as_of_date, date):
            raise TypeError("context as-of date must be a date")
        if not isinstance(self.dryrun, bool):
            raise TypeError("context dryrun must be Boolean")
        if not isinstance(self.frame, Frame):
            raise TypeError("context frame must be a Frame")
        if not isinstance(self.logger, logging.Logger):
            raise TypeError("context logger must be a Logger")
        if not isinstance(self.raw_params, CliParams):
            raise TypeError("context raw params must be CliParams")
