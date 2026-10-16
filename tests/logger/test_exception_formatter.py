"""Public formatters preserve original records and useful external stack evidence."""

import logging
from types import FunctionType

import pytest

from lclang.error import LclError, LclValidationError
from lclang.lang import define_frame, define_module
from lclang.logger import LclExceptionFormatter, LoggerHandlerConfig, resolve_logger_config
from lclang.logger.frame_logger_config import verbose_config


@pytest.mark.parametrize(
    "value,code", [(None, "LCL611113"), (False, "LCL611113"), ("other", "LCL611293")]
)
def test_traceback_policy_rejects_invalid_values_without_coercion(value: object, code: str) -> None:
    """Both public configuration and external formatter validate the same policy."""
    for constructor in (LoggerHandlerConfig, LclExceptionFormatter):
        with pytest.raises(LclValidationError) as caught:
            constructor(traceback_style=value)  # type: ignore[arg-type]
        assert caught.value.code == code and "traceback_style" in str(caught.value)


@pytest.mark.asyncio
async def test_compact_frames_use_module_identity_and_full_restores_language_frames() -> None:
    """An external callback whose filename contains lclang remains in the compact stack."""

    def fail() -> None:
        raise ValueError("external calculation failed")

    callback = FunctionType(
        fail.__code__.replace(co_filename="lclang/application.py"), {"__name__": "application"}
    )
    async with define_frame(
        define_module("external", {"RESULT": "fail()"}), preset={"fail": callback}
    ) as frame:
        with pytest.raises(LclError) as caught:
            await frame.get("RESULT")
    error = caught.value
    error.verbose_failure_id = "F-external"
    original_tb = error.__traceback__
    record = logging.makeLogRecord(
        {"msg": "request failed", "exc_info": (type(error), error, original_tb)}
    )
    compact = LclExceptionFormatter("%(message)s").format(record)
    full = LclExceptionFormatter("%(message)s", traceback_style="full").format(record)
    assert (
        compact.count("Error in evaluating RESULT") == full.count("Error in evaluating RESULT") == 1
    )
    compact_stack = compact.split("Python traceback:\n", 1)[1]
    assert 'File "lclang/application.py"' in compact_stack
    assert (
        "binding_evaluation.py" not in compact_stack and "operation_guard.py" not in compact_stack
    )
    assert "binding_evaluation.py" in full and "operation_guard.py" in full
    assert "ValueError: external calculation failed" in compact_stack
    assert "failure F-external" in compact_stack
    assert error.__traceback__ is original_tb and record.exc_text is None


def test_standard_layout_arguments_and_empty_exception_tuple_remain_supported() -> None:
    """External callers choose layouts without changing their producer's severity."""
    record = logging.makeLogRecord(
        {"msg": "read", "levelno": logging.DEBUG, "levelname": "DEBUG", "lclang_verbose": True}
    )
    formatter = LclExceptionFormatter(
        "{levelname} {application} {message}", style="{", defaults={"application": "app"}
    )
    assert formatter.format(record) == "TRACE app read"
    assert LclExceptionFormatter("$levelname $message", style="$").format(record) == "TRACE read"
    assert formatter.formatException((None, None, None)) == ""
    assert record.levelname == "DEBUG" and record.levelno == logging.DEBUG
    assert logging.getLevelName(logging.DEBUG) == "DEBUG"


@pytest.mark.asyncio
async def test_frame_traceback_policy_survives_verbose_threshold_changes() -> None:
    """Frame and Python declarations carry the same full policy through verbose conversion."""
    async with define_frame(
        define_module("logging", {"logger.traceback_style": "'full'"})
    ) as frame:
        config = await resolve_logger_config(frame, verbose=True)
    assert config.traceback_style == "full"
    assert verbose_config(LoggerHandlerConfig(traceback_style="full")).traceback_style == "full"
