"""Executable unit cases for the business-day-calendars tutorial."""

from tests.tutorials.support import execute_tutorial


def test_business_day_calendar_examples() -> None:
    """Composition, mapping, and isolated JSON loading return expected dates."""
    execute_tutorial("11-business-day-calendars.md", 3)

