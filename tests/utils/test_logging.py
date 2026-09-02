"""Behavioural tests for standalone configured logging utilities."""

import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.utils import DEFAULT_LOG_FORMAT, LogConfig, LoggerHandle, create_logger


def test_standalone_logger_uses_config_and_owns_cleanup() -> None:
    """Downstream callers can log without constructing CLI or Frame values."""
    assert "%(message)s" in DEFAULT_LOG_FORMAT
    disabled = asyncio.run(create_logger(LogConfig(), "downstream.disabled"))
    assert isinstance(disabled, LoggerHandle)
    assert isinstance(disabled.handlers[0], logging.NullHandler)
    assert disabled.logger.name == "downstream.disabled"
    disabled.close()
    disabled.close()
    assert disabled.logger.handlers == []

    with TemporaryDirectory(prefix="lclang-utility-logger-") as directory:
        config = LogConfig(
            log_dir=directory,
            log_file_name="downstream.log",
            log_format=(
                "%(asctime)s %(levelname)s %(filename)s:%(lineno)d "
                "%(funcName)s %(message)s"
            ),
        )
        handle = asyncio.run(create_logger(config, "downstream.enabled"))
        handle.logger.info("standalone message")
        handle.close()
        assert handle.log_path == Path(directory) / "downstream.log"
        assert "standalone message" in handle.log_path.read_text(encoding="utf-8")


def test_standalone_logger_rejects_invalid_public_arguments() -> None:
    """The standalone factory validates its configuration and exact logger name."""
    with pytest.raises(TypeError, match="LogConfig"):
        asyncio.run(create_logger(object(), "invalid"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="text"):
        asyncio.run(create_logger(LogConfig(), 1))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(create_logger(LogConfig(), ""))
