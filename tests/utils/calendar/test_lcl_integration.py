"""Executable LCL integration contract for business-day calendars."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from lclang.config import load_config
from lclang.types import FrameId
from lclang.utils.calendar import BDCalendar, BDCalendarMapping, DayType

# Static LCL policies used by calendar integration tests.
FIXTURES = Path(__file__).with_name("fixtures")


@pytest.mark.asyncio
async def test_lcl_builds_adjusted_report_calendar_and_execution_mapping(
    tmp_path: Path,
) -> None:
    """LCL auto-awaits loading, mapping materialization, and calendar composition."""
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    (calendars / "CN_TRADING_DAYS.calendar.json").write_text(
        json.dumps(
            {
                "business_days": ["20240116", "20240117", "20240131", "20240201"],
                "holidays": ["20240115"],
            }
        ),
        encoding="utf-8",
    )
    source = tmp_path / "reports.lclcfg"
    source.write_text(
        "__LCL_VERSION__: 1\n"
        'hardcoded_calendar_dir: f"{__dir__}/calendars"\n'
        "calendar_mgr: use_calendar_manager(["
        "use_file_system_hardcoded_calendar_loader(hardcoded_calendar_dir)])\n"
        'CN_TRADING_DAYS: calendar_mgr.use_calendar("CN_TRADING_DAYS")\n'
        'LOADED_ALL_DAYS: calendar_mgr.use_calendar("ALL_DAYS")\n'
        "BUILTIN_ALL_DAYS: calendars.ALL_DAYS\n"
        "BUSINESS_DAY_TYPE: calendars.DayType.BusinessDay\n"
        "REPORT_DAYS: calendars.nth_day_of_month(15)"
        ".map_this_or_next(CN_TRADING_DAYS).as_calendar() + calendars.END_OF_MONTHS\n"
        "REPORT_EXECUTION_MAPPING: REPORT_DAYS.shift_n_days(1, CN_TRADING_DAYS)\n",
        encoding="utf-8",
    )
    config = await load_config(source)
    async with config.frame_factory().create(FrameId("calendar-example")) as frame:
        report = await frame.get("REPORT_DAYS")
        mapping = await frame.get("REPORT_EXECUTION_MAPPING")
        loaded_all_days = await frame.get("LOADED_ALL_DAYS")
        builtin_all_days = await frame.get("BUILTIN_ALL_DAYS")
        assert isinstance(report, BDCalendar)
        assert isinstance(mapping, BDCalendarMapping)
        assert loaded_all_days is builtin_all_days
        assert await frame.get("BUSINESS_DAY_TYPE") is DayType.BusinessDay
        assert await report.get_day_type(date(2024, 1, 16)) is DayType.BusinessDay
        assert await report.get_day_type(date(2024, 1, 31)) is DayType.BusinessDay
        assert await mapping.map_date(date(2024, 1, 16)) == date(2024, 1, 17)
        assert await mapping.map_date_reverse(date(2024, 1, 17)) == (
            date(2024, 1, 16),
            date(2024, 1, 16),
        )


@pytest.mark.asyncio
async def test_lcl_salary_calendar_classifies_every_date_in_2026() -> None:
    """LCL moves a holiday 20th to the latest preceding weekday for all of 2026."""
    config = await load_config(FIXTURES / "salary_2026.lclcfg")
    expected_salary_days = frozenset(
        {
            date(2026, 1, 20),
            date(2026, 2, 20),
            date(2026, 3, 20),
            date(2026, 4, 20),
            date(2026, 5, 20),
            date(2026, 6, 19),
            date(2026, 7, 20),
            date(2026, 8, 20),
            date(2026, 9, 18),
            date(2026, 10, 20),
            date(2026, 11, 20),
            date(2026, 12, 18),
        }
    )
    async with config.frame_factory().create(FrameId("salary-2026")) as frame:
        salary_calendar = await frame.get("SALARY_DAYS")
        assert isinstance(salary_calendar, BDCalendar)
        first = date(2026, 1, 1)
        for offset in range(365):
            current = first + timedelta(days=offset)
            expected = (
                DayType.BusinessDay
                if current in expected_salary_days
                else DayType.Holiday
            )
            assert await salary_calendar.get_day_type(current) is expected
