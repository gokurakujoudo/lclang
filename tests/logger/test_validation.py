"""Rainy configuration cases and detached declared defaults."""

import io
from collections.abc import Mapping

import pytest

from lclang.logger import LoggerHandlerConfig
from lclang.logger.config import handler_config


@pytest.mark.parametrize(
    "value",
    [
        None,
        {1: "value"},
        {"unknown": 1},
        {"format": 1},
        {"level": -1},
        {"level": True},
        {"takeover_loggers": "root"},
        {"takeover_loggers": [""]},
        {"console": {"stream": "other"}},
        {"file": {"bad-name": {"enabled": False}}},
    ],
)
def test_invalid_top_level_declarations(value: object) -> None:
    """Reject invalid public shapes with no side effects."""
    with pytest.raises((TypeError, ValueError)):
        handler_config(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "fields",
    [
        {"directory": 1},
        {"filename": ""},
        {"filename": "."},
        {"filename": "{other}.log"},
        {"filename": "{pid:04d}.log"},
        {"filename": "{pid!r}.log"},
        {"filename": "{unclosed"},
        {"encoding": 1},
        {"encoding": "no-such-encoding"},
        {"flush_interval": False},
        {"flush_interval": "1"},
        {"flush_interval": 0},
        {"flush_interval": float("inf")},
        {"flush_interval": float("nan")},
        {"logger_names": [1]},
        {"rotation": {"mode": "other"}},
        {"rotation": {"max_bytes": -1}},
        {"rotation": {"max_bytes": True}},
        {"rotation": {"mode": "size"}},
        {"rotation": {"mode": "time"}},
        {"rotation": {"interval": 1}},
        {"rotation": {"interval": "0d"}},
        {"rotation": {"interval": "2h", "align": True}},
        {"rotation": {"align": True}},
    ],
)
def test_invalid_file_fields(fields: dict[str, object]) -> None:
    """Disabled outputs still validate supplied field types and policies."""
    with pytest.raises((TypeError, ValueError, LookupError)):
        LoggerHandlerConfig(file={"app": {"enabled": False, **fields}})


def test_declarations_are_frozen_and_rotation_templates_are_partial() -> None:
    """Templates can defer required fields to individual sinks without losing them."""
    files: dict[str, dict[str, object]] = {
        "default": {"rotation": {"mode": "size"}},
        "app": {
            "enabled": False,
            "rotation": {"max_bytes": 100},
            "logger_names": [],
        },
    }
    config = LoggerHandlerConfig(console={"stream": io.StringIO()}, file=files)
    files["default"]["rotation"] = {"mode": "none"}
    assert config.resolved_files()["app"].rotation.mode == "size"
    assert isinstance(config.file["app"], Mapping)
    with pytest.raises(TypeError):
        config.file["app"]["enabled"] = True  # type: ignore[index]


@pytest.mark.parametrize(
    "config,path",
    [
        ({"format": "plain"}, "logger.format"),
        (
            {"file": {"app": {"enabled": False, "filename": "{unclosed"}}},
            "logger.file.app.filename",
        ),
        (
            {"file": {"app": {"enabled": False, "encoding": "no-such-encoding"}}},
            "logger.file.app.encoding",
        ),
    ],
)
def test_library_validation_errors_include_field(config: dict[str, object], path: str) -> None:
    """Stdlib validation failures retain the public configuration path."""
    with pytest.raises(ValueError, match=path):
        handler_config(config)
