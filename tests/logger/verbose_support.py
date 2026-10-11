"""Application-owned logging destinations shared by verbose behavior tests."""

import io
import logging


class RecordCapture(logging.Handler):
    """Keep original records so tests can inspect detached producer metadata."""

    def __init__(self) -> None:
        """Start with an empty producer record list."""
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def capture_logger(level: int = logging.DEBUG) -> tuple[logging.Logger, io.StringIO]:
    """Build a detached logger with an application-owned text handler."""
    output = io.StringIO()
    logger = logging.Logger("application.verbose", level)
    logger.addHandler(logging.StreamHandler(output))
    return logger, output
