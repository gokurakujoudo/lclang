"""Readable display labels do not change standard logging semantics."""

import logging

import pytest

from lclang.logger import LclExceptionFormatter
from lclang.logger.handler_config import DEFAULT_FORMAT
from lclang.logger.record_formatter import RecordFormatter


def test_verbose_label_and_default_prefix_are_formatter_only() -> None:
    """Producer records retain DEBUG while displayed verbose omits Python locations."""
    record = logging.LogRecord("app.engine", logging.DEBUG, "engine.py", 17, "read total", (), None)
    record.funcName = "evaluate_definition"
    record.lclang_verbose = True
    text = RecordFormatter(DEFAULT_FORMAT).format(record)
    assert f" | TRACE | {record.threadName}({record.process}) | read total" in text
    assert "app.engine" not in text and "engine.py" not in text
    assert "evaluate_definition" not in text
    assert record.levelno == logging.DEBUG and record.levelname == "DEBUG"
    assert record.msg == "read total"


def test_custom_format_keeps_fields_but_uses_verbose_display_label() -> None:
    """A user-selected logger name remains available without global level renaming."""
    record = logging.LogRecord("custom", logging.DEBUG, "engine.py", 17, "read", (), None)
    record.lclang_verbose = True
    assert RecordFormatter("%(name)s %(levelname)s %(message)s").format(record) == (
        "custom TRACE read"
    )
    assert logging.getLevelName(logging.DEBUG) == "DEBUG"


def test_workflow_default_layouts_keep_business_locations_only() -> None:
    """Only default marked layouts omit names while explicit layouts remain authoritative."""
    record = logging.LogRecord(
        "fixed.framework", logging.INFO, "business.py", 23, "message", (), None
    )
    record.funcName = "publish"
    record.lclang_workflow_lifecycle = True
    lifecycle = RecordFormatter(DEFAULT_FORMAT).format(record)
    assert f" | INFO  | {record.threadName}({record.process}) | message" in lifecycle
    assert "fixed.framework" not in lifecycle and "business.py" not in lifecycle
    record.lclang_workflow_lifecycle = False
    record.lclang_event = "saved"
    event = RecordFormatter(DEFAULT_FORMAT).format(record)
    assert "fixed.framework" not in event
    assert "business.py:23:publish | message" in event
    assert RecordFormatter("%(name)s %(filename)s %(message)s").format(record) == (
        "fixed.framework business.py message"
    )
    assert record.name == "fixed.framework" and record.msg == "message"


@pytest.mark.parametrize(
    "level,original,display",
    [
        (logging.NOTSET, "NOTSET", "UNSET"),
        (logging.DEBUG, "DEBUG", "DEBUG"),
        (logging.INFO, "INFO", "INFO"),
        (logging.WARNING, "WARNING", "WARN"),
        (logging.ERROR, "ERROR", "ERROR"),
        (logging.CRITICAL, "CRITICAL", "CRIT"),
        (35, "APPLICATION_LEVEL", "APPLICATION_LEVEL"),
    ],
)
def test_display_levels_preserve_records_and_standard_level_names(
    level: int, original: str, display: str
) -> None:
    """All formatter styles abbreviate display names without changing borrowed records."""
    record = logging.LogRecord("app", level, "business.py", 23, "value %s\nnext", (3,), None)
    record.levelname = original
    record.funcName = "publish"
    record.process, record.threadName, record.created = 123456, "MainThread", 0
    before = record.__dict__.copy()
    formatters = (
        RecordFormatter("%(levelname)s %(filename)s %(message)s"),
        LclExceptionFormatter("%(levelname)s %(filename)s %(message)s"),
        LclExceptionFormatter("{levelname} {filename} {message}", style="{"),
        LclExceptionFormatter("$levelname $filename $message", style="$"),
    )
    for formatter in formatters:
        assert formatter.format(record) == f"{display} business.py value 3\nnext"
        assert record.__dict__ == before
    assert RecordFormatter(DEFAULT_FORMAT, timezone="utc").format(record) == (
        f"1970-01-01T00:00:00.000000Z | {display:<5} | MainThread(123456) | "
        "app | business.py:23:publish | value 3\nnext"
    )
    assert record.__dict__ == before
    if level != 35:
        assert logging.getLevelName(level) == original
