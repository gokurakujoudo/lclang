"""Configuration inheritance and input validation."""

import logging
from pathlib import Path

import pytest

from lclang.logger import LoggerHandlerConfig


def test_templates_preserve_false_and_explicit_true() -> None:
    """Defaults fill missing fields without replacing explicit exceptions."""
    config = LoggerHandlerConfig(
        file={
            "default": {"enabled": False, "level": "ERROR", "directory": "."},
            "app": {"filename": "app.{pid}.log"},
            "audit": {"enabled": True, "level": "DEBUG"},
        }
    )
    sinks = config.resolved_files()
    assert set(sinks) == {"app", "audit"}
    assert not sinks["app"].enabled
    assert sinks["audit"].enabled and sinks["audit"].level == logging.DEBUG
    assert sinks["audit"].directory == Path(".")
    assert not LoggerHandlerConfig(file={"default": {"enabled": False}}).resolved_files()


@pytest.mark.parametrize(
    "config",
    [
        {"level": "NOPE"},
        {"capture_warnings": "False"},
        {"console": {"enabled": "False"}},
        {"console": {"unknown": 1}},
        {"file": {"app": {"enabled": True}}},
        {"file": {"app": {"enabled": False, "filename": "../bad"}}},
    ],
)
def test_invalid_configs_fail_before_io(config: dict[str, object]) -> None:
    """Invalid declarations cannot silently disable or misroute logs."""
    with pytest.raises((TypeError, ValueError)):
        LoggerHandlerConfig(**config)  # type: ignore[arg-type]
