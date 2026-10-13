"""Failing DEBUG destinations shared by verbose isolation tests."""

import logging
from typing import Any


class FailingVerboseLogger(logging.Logger):
    """Fail one DEBUG boundary while leaving ordinary lifecycle logging available."""

    def __init__(self, boundary: str, failure: BaseException | None = None) -> None:
        """Select the failing boundary and retain the exact failure instance."""
        super().__init__("failing-verbose", logging.DEBUG)
        self.boundary = boundary
        self.failure = RuntimeError("verbose destination failed") if failure is None else failure
        self.addHandler(logging.NullHandler())
        if boundary == "handler":
            self.addHandler(FailingDebugHandler(self.failure))

    def isEnabledFor(self, level: int) -> bool:
        if level == logging.DEBUG and self.boundary == "probe":
            raise self.failure
        return super().isEnabledFor(level)

    def debug(self, msg: object, *args: object, **kwargs: Any) -> None:
        if self.boundary == "write":
            raise self.failure
        super().debug(msg, *args, **kwargs)


class FailingDebugHandler(logging.Handler):
    """Raise during handler processing only for DEBUG records."""

    def __init__(self, failure: BaseException) -> None:
        """Retain the exact failure used to test propagation or isolation."""
        super().__init__()
        self.failure = failure

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno == logging.DEBUG:
            raise self.failure
