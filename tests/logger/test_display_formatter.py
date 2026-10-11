"""Readable display labels do not change standard logging semantics."""

import logging

from lclang.logger.handler_config import DEFAULT_FORMAT
from lclang.logger.record_formatter import RecordFormatter


def test_verbose_label_and_default_prefix_are_formatter_only() -> None:
    """Producer records retain DEBUG while displayed verbose omits Python locations."""
    record = logging.LogRecord("app.engine", logging.DEBUG, "engine.py", 17, "read total", (), None)
    record.funcName = "evaluate_definition"
    record.lclang_verbose = True
    text = RecordFormatter(DEFAULT_FORMAT).format(record)
    assert "VERBOSE" in text and "pid=" in text and "thread=" in text
    assert "app.engine" not in text and "engine.py" not in text
    assert "evaluate_definition" not in text
    assert record.levelno == logging.DEBUG and record.levelname == "DEBUG"
    assert record.msg == "read total"


def test_custom_format_keeps_fields_but_uses_verbose_display_label() -> None:
    """A user-selected logger name remains available without global level renaming."""
    record = logging.LogRecord("custom", logging.DEBUG, "engine.py", 17, "read", (), None)
    record.lclang_verbose = True
    assert RecordFormatter("%(name)s %(levelname)s %(message)s").format(record) == (
        "custom VERBOSE read"
    )
    assert logging.getLevelName(logging.DEBUG) == "DEBUG"
