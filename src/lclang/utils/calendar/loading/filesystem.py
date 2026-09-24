"""Strict JSON hardcoded-calendar filesystem loader."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast, final

from lclang.stdlib.dates import parse_ymd
from lclang.utils.calendar.base import BDCalendar
from lclang.utils.calendar.errors import CalendarCannotLoadException
from lclang.utils.calendar.hardcoded import HardcodedBDCalendar
from lclang.utils.calendar.loading.base import BDCalendarLoader
from lclang.utils.calendar.types import CalendarID, DayType

if TYPE_CHECKING:
    from lclang.utils.calendar.loading.manager import BDCalendarManager


def read_calendar_json(path: Path, calendar_id: CalendarID) -> HardcodedBDCalendar:
    """Read and validate one strict hardcoded-calendar JSON document.

    :param path: Existing regular JSON file.
    :param calendar_id: Identifier assigned to the result calendar.
    :returns: Loaded hardcoded calendar.
    :raises OSError: If the file cannot be read.
    :raises ValueError: If JSON content violates the strict schema.
    """
    raw = json.loads(path.read_bytes().decode("utf-8-sig"))
    if not isinstance(raw, dict) or set(cast(dict[object, object], raw)) != {
        "business_days",
        "holidays",
    }:
        raise ValueError("calendar JSON requires exactly business_days and holidays")
    data = cast(dict[str, object], raw)
    business = data["business_days"]
    holidays = data["holidays"]
    if not isinstance(business, list) or not isinstance(holidays, list):
        raise ValueError("calendar JSON fields must be arrays")
    if any(
        not isinstance(value, str)
        for value in (*cast(list[object], business), *cast(list[object], holidays))
    ):
        raise ValueError("calendar JSON dates must be YYYYMMDD strings")
    business = cast(list[str], business)
    holidays = cast(list[str], holidays)
    if len(set(business)) != len(business) or len(set(holidays)) != len(holidays):
        raise ValueError("calendar JSON dates cannot repeat")
    if set(business) & set(holidays):
        raise ValueError("calendar JSON business days and holidays cannot overlap")
    defined = {parse_ymd(value): DayType.BusinessDay for value in business}
    defined.update({parse_ymd(value): DayType.Holiday for value in holidays})
    return HardcodedBDCalendar(calendar_id, defined)


@final
class FileSystemHardcodedBDCalendarLoader(BDCalendarLoader):
    """Load strict hardcoded calendar JSON files from one directory.

    :param hardcoded_calendar_dir: Directory containing ``*.calendar.json`` files.
    """

    __slots__ = ("hardcoded_calendar_dir",)

    def __init__(self, hardcoded_calendar_dir: Path) -> None:
        """Create a path-contained filesystem loader.

        :param hardcoded_calendar_dir: Directory containing calendar files.
        :returns: ``None``.
        :raises TypeError: If the directory is not a :class:`Path`.
        """
        if not isinstance(hardcoded_calendar_dir, Path):
            raise TypeError("hardcoded calendar directory must be a Path")
        self.hardcoded_calendar_dir = hardcoded_calendar_dir.resolve(strict=False)

    async def load_calendar(
        self,
        calendar_id: CalendarID,
        manager: BDCalendarManager,
    ) -> BDCalendar | None:
        """Load one contained strict JSON calendar.

        :param calendar_id: Requested calendar identifier.
        :param manager: Unused manager retained for loader symmetry.
        :returns: Loaded hardcoded calendar or ``None`` when absent.
        :raises CalendarCannotLoadException: If matching content is invalid.
        """
        del manager
        if Path(str(calendar_id)).name != str(calendar_id):
            return None
        path = (self.hardcoded_calendar_dir / f"{calendar_id}.calendar.json").resolve(strict=False)
        if not path.is_relative_to(self.hardcoded_calendar_dir):
            return None
        if not path.exists():
            return None
        if not path.is_file():
            raise CalendarCannotLoadException(calendar_id)
        try:
            return await asyncio.to_thread(read_calendar_json, path, calendar_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise CalendarCannotLoadException(calendar_id) from error


def use_file_system_hardcoded_calendar_loader(
    hardcoded_calendar_dir: Path | str,
) -> FileSystemHardcodedBDCalendarLoader:
    """Create a strict filesystem hardcoded-calendar loader.

    :param hardcoded_calendar_dir: Directory path accepted as text or :class:`Path`.
    :returns: Filesystem calendar loader.
    """
    return FileSystemHardcodedBDCalendarLoader(Path(hardcoded_calendar_dir))
