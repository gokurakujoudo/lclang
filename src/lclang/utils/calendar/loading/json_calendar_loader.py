"""Strict JSON hardcoded-calendar filesystem loader.

Defines ``read_calendar_json``, ``FileSystemHardcodedBDCalendarLoader``,
``use_file_system_hardcoded_calendar_loader``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast, final

from lclang.error import LclError, LclUtilityError, UtilityErrorCode
from lclang.error.calendar_exception import CalendarCannotLoadException, wrap_calendar_failure
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID, DayType
from lclang.utils.calendar.hardcoded_calendar import HardcodedBDCalendar
from lclang.utils.calendar.loading.calendar_loader import BDCalendarLoader

if TYPE_CHECKING:
    from lclang.utils.calendar.loading.calendar_manager import BDCalendarManager


@guard_failure(LclUtilityError, UtilityErrorCode.E12_CALENDAR_LOADING_NATIVE_FAILURE)
def read_calendar_json(path: Path, calendar_id: CalendarID) -> HardcodedBDCalendar:
    """Read and validate one strict hardcoded-calendar JSON document.

    :param path: Existing regular JSON file.
    :param calendar_id: Identifier assigned to the result calendar.
    :returns: Loaded hardcoded calendar.
    :raises OSError: If the file cannot be read.
    :raises LclValidationError: If JSON content violates the strict schema.
    """
    from lclang.lang.stdlib.date_conversion import parse_ymd

    raw = json.loads(path.read_bytes().decode("utf-8-sig"))
    if not isinstance(raw, dict) or set(cast(dict[object, object], raw)) != {
        "business_days",
        "holidays",
    }:
        raise LclValidationError(
            "calendar JSON requires exactly business_days and holidays",
            code=UtilityErrorCode.E12_CALENDAR_JSON_REQUIRES_EXACTLY_BUSINESS_DAYS_AND_HOLIDAYS,
        )
    data = cast(dict[str, object], raw)
    business = data["business_days"]
    holidays = data["holidays"]
    if not isinstance(business, list) or not isinstance(holidays, list):
        raise LclValidationError(
            "calendar JSON fields must be arrays",
            code=UtilityErrorCode.E12_CALENDAR_JSON_FIELDS_MUST_BE_ARRAYS,
        )
    if any(
        not isinstance(value, str)
        for value in (*cast(list[object], business), *cast(list[object], holidays))
    ):
        raise LclValidationError(
            "calendar JSON dates must be YYYYMMDD strings",
            code=UtilityErrorCode.E12_CALENDAR_JSON_DATES_MUST_BE_YYYYMMDD_STRINGS,
        )
    business = cast(list[str], business)
    holidays = cast(list[str], holidays)
    if len(set(business)) != len(business) or len(set(holidays)) != len(holidays):
        raise LclValidationError(
            "calendar JSON dates cannot repeat",
            code=UtilityErrorCode.E12_CALENDAR_JSON_DATES_CANNOT_REPEAT,
        )
    if set(business) & set(holidays):
        raise LclValidationError(
            "calendar JSON business days and holidays cannot overlap",
            code=UtilityErrorCode.E12_CALENDAR_JSON_BUSINESS_DAYS_AND_HOLIDAYS_CANNOT_OVERLAP,
        )
    defined = {parse_ymd(value): DayType.BusinessDay for value in business}
    defined.update({parse_ymd(value): DayType.Holiday for value in holidays})
    return HardcodedBDCalendar(calendar_id, defined)


@guard_constructor(LclValidationError, UtilityErrorCode.E12_CALENDAR_LOADING_NATIVE_FAILURE)
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
        :raises LclValidationError: If the directory is not a :class:`Path`.
        """
        if not isinstance(hardcoded_calendar_dir, Path):
            raise LclValidationError(
                "hardcoded calendar directory must be a Path",
                code=UtilityErrorCode.E12_HARDCODED_CALENDAR_DIRECTORY_MUST_BE_A_PATH,
            )
        self.hardcoded_calendar_dir = hardcoded_calendar_dir.resolve(strict=False)

    @guard_async_failure(LclUtilityError, UtilityErrorCode.E12_CALENDAR_LOADING_NATIVE_FAILURE)
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
            raise CalendarCannotLoadException(
                calendar_id, code=UtilityErrorCode.E12_LOAD_CALENDAR_FAILURE
            )
        try:
            return await asyncio.to_thread(read_calendar_json, path, calendar_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            failure = wrap_calendar_failure(
                error,
                CalendarCannotLoadException(
                    calendar_id,
                    code=(
                        error.code
                        if isinstance(error, LclError)
                        else UtilityErrorCode.E12_LOAD_CALENDAR_FAILURE
                    ),
                ),
            )
            raise failure from failure.__cause__


@guard_failure(LclUtilityError, UtilityErrorCode.E12_CALENDAR_LOADING_NATIVE_FAILURE)
def use_file_system_hardcoded_calendar_loader(
    hardcoded_calendar_dir: Path | str,
) -> FileSystemHardcodedBDCalendarLoader:
    """Create a strict filesystem hardcoded-calendar loader.

    :param hardcoded_calendar_dir: Directory path accepted as text or :class:`Path`.
    :returns: Filesystem calendar loader.
    """
    return FileSystemHardcodedBDCalendarLoader(Path(hardcoded_calendar_dir))
