"""Event-time timezone formatting and configuration contracts."""

import asyncio
import io
import logging
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, Self
from unittest.mock import patch

import pytest

from lclang import define_frame, define_module
from lclang.logger import LoggerHandlerConfig, resolve_logger_config, use_logger_handler
from lclang.logger.config import handler_config
from lclang.logger.formatter import RecordFormatter


class ServerDatetime(datetime):
    """Simulate OS local conversion using real datetime arithmetic and event offsets."""

    offset = 8

    def astimezone(self, tz: tzinfo | None = None) -> Self:
        assert tz is None
        return super().astimezone(timezone(timedelta(hours=self.offset)))


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (8, "2026-01-02T07:30:00.125000+08:00"),
        (-5, "2026-01-01T18:30:00.125000-05:00"),
        (0, "2026-01-01T23:30:00.125000+00:00"),
    ],
)
def test_formatter_uses_local_offset_without_mutating_record(offset: int, expected: str) -> None:
    """Local conversion retains microseconds, date rollover, and explicit zero offset."""
    record = logging.makeLogRecord(
        {
            "created": datetime(2026, 1, 1, 23, 30, 0, 125000, UTC).timestamp(),
            "msg": "value=%s",
            "args": (3,),
            "lclang_prefix": "[TEST]",
        }
    )
    original = record.__dict__.copy()
    with (
        patch("lclang.logger.formatter.datetime", ServerDatetime),
        patch.object(ServerDatetime, "offset", offset),
    ):
        assert RecordFormatter("%(asctime)s %(message)s").format(record) == (
            expected + " [TEST] value=3"
        )
        assert RecordFormatter("%(message)s").format(record) == "[TEST] value=3"
        assert RecordFormatter("%(asctime)s", timezone="utc").format(record) == (
            "2026-01-01T23:30:00.125000Z"
        )
    assert record.__dict__ == original


def test_local_conversion_uses_each_event_at_dst_fallback() -> None:
    """An isolated OS boundary simulation distinguishes the repeated local hour."""

    class FallBackDatetime(datetime):
        def astimezone(self, tz: tzinfo | None = None) -> Self:
            assert tz is None
            offset = -4 if self.hour < 6 else -5
            return super().astimezone(timezone(timedelta(hours=offset)))

    formatter = RecordFormatter("%(asctime)s")
    with patch("lclang.logger.formatter.datetime", FallBackDatetime):
        for hour, expected in (
            (5, "2026-11-01T01:30:00.125000-04:00"),
            (6, "2026-11-01T01:30:00.125000-05:00"),
        ):
            record = logging.makeLogRecord(
                {"created": datetime(2026, 11, 1, hour, 30, 0, 125000, UTC).timestamp()}
            )
            assert formatter.format(record) == expected


@pytest.mark.asyncio
async def test_sinks_and_successive_scopes_share_selected_timezone() -> None:
    """File and console agree, and policy does not leak between process scopes."""
    record = logging.makeLogRecord(
        {"created": 0.125, "msg": "ready", "levelno": logging.INFO, "name": "app"}
    )
    with TemporaryDirectory() as directory:
        for policy, expected in (
            ("utc", "1970-01-01T00:00:00.125000Z ready"),
            ("local", "1970-01-01T08:00:00.125000+08:00 ready"),
            ("utc", "1970-01-01T00:00:00.125000Z ready"),
        ):
            stream = io.StringIO()
            with patch("lclang.logger.formatter.datetime", ServerDatetime):
                async with use_logger_handler(
                    {
                        "timezone": policy,
                        "format": "%(asctime)s %(message)s",
                        "console": {"stream": stream},
                        "file": {"app": {"directory": directory}},
                    }
                ) as runtime:
                    logging.getLogger().handle(record)
            assert stream.getvalue() == expected + "\n"
            path = runtime.metrics.sinks["file.app"].path
            assert path is not None
            assert path.read_text().splitlines()[1:] == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value, error",
    [
        (None, TypeError),
        (True, TypeError),
        (1, TypeError),
        ("UTC", ValueError),
        ("", ValueError),
        ("Asia/Shanghai", ValueError),
    ],
)
async def test_invalid_timezone_fails_before_file_creation(
    value: object, error: type[Exception]
) -> None:
    """Invalid policies report their field before creating enabled file sinks."""
    with TemporaryDirectory() as directory:
        with pytest.raises(error, match="logger.timezone"):
            async with use_logger_handler(
                {"timezone": value, "file": {"app": {"directory": directory}}}
            ):
                pytest.fail("invalid timezone entered a handler scope")
        assert await asyncio.to_thread(lambda: list(Path(directory).iterdir())) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", ["local", "utc"])
@pytest.mark.parametrize("verbose", [False, True])
async def test_configuration_paths_preserve_timezone(
    policy: Literal["local", "utc"], verbose: bool
) -> None:
    """Objects, mappings, scoped overrides and verbose share one timestamp policy."""
    assert LoggerHandlerConfig().timezone == "local"
    assert handler_config({}).timezone == "local"
    assert handler_config({"timezone": policy}).timezone == policy
    assert LoggerHandlerConfig(timezone=policy).timezone == policy
    async with (
        define_frame(define_module("base", {"logger.timezone": '"utc"'})) as parent,
        parent.derive(define_module("override", {}), values={"logger.timezone": policy}) as frame,
    ):
        assert (await resolve_logger_config(frame, verbose)).timezone == policy


@pytest.mark.asyncio
async def test_timezone_error_retains_source() -> None:
    """Invalid Frame values identify their defining source."""
    async with define_frame(define_module("bad_timezone", {"logger.timezone": '"UTC"'})) as frame:
        with pytest.raises(ValueError, match="logger.timezone.*bad_timezone"):
            await resolve_logger_config(frame)
