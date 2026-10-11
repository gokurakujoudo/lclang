"""Framework-only exception formatting leaves application logging unchanged."""

import logging

from lclang.error import LclError
from lclang.logger.record_formatter import RecordFormatter


def test_framework_formatting_does_not_mutate_shared_exception_record() -> None:
    """A complete message appears once while Python traceback leaves are references."""
    error = LclError("diagnostic payload", code="APP/FORMAT")
    error.verbose_failure_id = "F-format"
    record = logging.makeLogRecord(
        {"msg": str(error), "exc_info": (LclError, error, None), "lclang_failure_diagnostic": True}
    )
    text = RecordFormatter("%(message)s").format(record)
    assert text.count("diagnostic payload") == 1
    assert "Python traceback:" not in text
    assert "[APP/FORMAT: diagnostic payload] (failure F-format)" in text
    assert record.exc_info is not None and record.exc_text is None
    # Standard logging can supply an empty exception tuple outside an except block.
    record.exc_info = (None, None, None)
    assert RecordFormatter("%(message)s").format(record) == str(error)
    record.exc_info = (LclError, error, None)
    record.lclang_failure_diagnostic = False
    assert RecordFormatter("%(message)s").format(record).count("diagnostic payload") == 2
