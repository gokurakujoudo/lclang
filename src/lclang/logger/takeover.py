"""Reversible root, named logger, and warnings configuration takeover."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Any

from lclang.logger.config import LoggerHandlerConfig
from lclang.logger.queue_handler import LocalQueueHandler


@dataclass(slots=True)
class LoggerState:
    """Retain configuration without owning or modifying borrowed handlers.

    :param logger: Target stdlib logger.
    :param handlers: Original handler list in original order.
    :param level: Original numeric level.
    :param propagate: Original parent propagation flag.
    :param disabled: Original disabled flag.
    :param filters: Original logger filter list.
    """

    logger: logging.Logger
    handlers: list[logging.Handler]
    level: int
    propagate: bool
    disabled: bool
    filters: list[logging.Filter | Any]

    def restore(self) -> None:
        """Restore exact borrowed objects and effective level caches."""
        self.logger.handlers = self.handlers
        self.logger.filters = self.filters
        self.logger.setLevel(self.level)
        self.logger.propagate = self.propagate
        self.logger.disabled = self.disabled


class LoggingTakeover:
    """Save all state before installing process-global logging changes."""

    def __init__(self, config: LoggerHandlerConfig, handler: LocalQueueHandler) -> None:
        """Capture named targets, including warning state before capture begins.

        :param config: Process configuration.
        :param handler: Queue handler replacing the root output.
        """
        self.config, self.handler = config, handler
        targets = [
            logging.getLogger(),
            *(logging.getLogger(name) for name in config.takeover_loggers),
        ]
        if config.capture_warnings:
            targets.append(logging.getLogger("py.warnings"))
        self.states = [
            LoggerState(
                item,
                item.handlers,
                item.level,
                item.propagate,
                item.disabled,
                item.filters,
            )
            for item in dict.fromkeys(targets)
        ]
        self.showwarning = warnings.showwarning
        # stdlib exposes no capture-state getter; preserve its saved callback for exact restoration.
        self.saved_warning = logging._warnings_showwarning  # type: ignore[attr-defined]

    def install(self) -> None:
        """Replace only selected targets while leaving borrowed handlers untouched."""
        for state in self.states:
            target = state.logger
            target.handlers = [self.handler] if target is logging.root else []
            target.filters = []
            target.setLevel(self.config.level if target is logging.root else logging.NOTSET)
            target.propagate = True
            target.disabled = False
        if self.config.capture_warnings:
            logging.captureWarnings(True)

    def restore(self) -> None:
        """Restore logging and the precise pre-scope warnings callback state."""
        for state in reversed(self.states):
            state.restore()
        if self.config.capture_warnings:
            warnings.showwarning = self.showwarning
            logging._warnings_showwarning = self.saved_warning  # type: ignore[attr-defined]
