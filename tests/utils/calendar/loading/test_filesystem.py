"""Calendar filesystem contracts."""

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from lclang.utils.calendar import (
    CalendarCannotLoadException,
    CalendarID,
    DayType,
    FileSystemHardcodedBDCalendarLoader,
    use_calendar_manager,
    use_file_system_hardcoded_calendar_loader,
)
from lclang.utils.calendar.loading.filesystem import read_calendar_json


@pytest.mark.parametrize(
    "content",
    (
        [],
        {"business_days": []},
        {"business_days": {}, "holidays": []},
        {"business_days": [1], "holidays": []},
        {"business_days": ["20240101", "20240101"], "holidays": []},
        {"business_days": ["20240101"], "holidays": ["20240101"]},
        {"business_days": ["bad"], "holidays": []},
    ),
)
def test_strict_calendar_json_rejects_every_schema_failure(
    tmp_path: Path,
    content: object,
) -> None:
    """Strict file parsing rejects malformed structure, dates, and overlap."""
    path = tmp_path / "BAD.calendar.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        read_calendar_json(path, CalendarID("BAD"))


@pytest.mark.asyncio
async def test_filesystem_loader_path_kinds_and_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filesystem loader declines unsafe paths and propagates cancellation."""
    with pytest.raises(TypeError):
        FileSystemHardcodedBDCalendarLoader(cast(Path, "bad"))
    loader = FileSystemHardcodedBDCalendarLoader(tmp_path)
    manager = use_calendar_manager((loader,))
    assert await loader.load_calendar(CalendarID("../BAD"), manager) is None
    assert await loader.load_calendar(CalendarID("MISSING"), manager) is None
    original_resolve = Path.resolve

    def escaped_resolve(path: Path, strict: bool = False) -> Path:
        if path.name == "ESCAPE.calendar.json":
            return tmp_path.parent / "outside.calendar.json"
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", escaped_resolve)
    assert await loader.load_calendar(CalendarID("ESCAPE"), manager) is None
    monkeypatch.setattr(Path, "resolve", original_resolve)
    (tmp_path / "DIR.calendar.json").mkdir()
    with pytest.raises(CalendarCannotLoadException):
        await loader.load_calendar(CalendarID("DIR"), manager)
    path = tmp_path / "CANCEL.calendar.json"
    path.write_text('{"business_days": [], "holidays": []}', encoding="utf-8")

    async def cancel_thread(function: object, *args: object) -> object:
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "to_thread", cancel_thread)
    with pytest.raises(asyncio.CancelledError):
        await loader.load_calendar(CalendarID("CANCEL"), manager)


@pytest.mark.asyncio
async def test_filesystem_loader_accepts_strict_json_and_rejects_bad_content(
    tmp_path: Path,
) -> None:
    """Filesystem loading parses strict date arrays and preserves causes."""
    good = tmp_path / "MARKET.calendar.json"
    good.write_text(
        json.dumps({"business_days": ["20240102"], "holidays": ["20240101"]}),
        encoding="utf-8",
    )
    loader = use_file_system_hardcoded_calendar_loader(tmp_path)
    manager = use_calendar_manager((loader,))
    calendar = await manager.use_calendar(CalendarID("MARKET"))
    assert await calendar.get_day_type(date(2024, 1, 2)) is DayType.BusinessDay
    assert await calendar.get_day_type(date(2024, 1, 1)) is DayType.Holiday
    bad = tmp_path / "BAD.calendar.json"
    bad.write_text('{"business_days": [], "holidays": [], "extra": []}', encoding="utf-8")
    with pytest.raises(CalendarCannotLoadException) as failure:
        await manager.use_calendar(CalendarID("BAD"))
    assert isinstance(failure.value.__cause__, ValueError)
    with pytest.raises(CalendarCannotLoadException):
        await manager.use_calendar(CalendarID("MISSING"))
