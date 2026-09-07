"""Calendar composition contracts."""

from datetime import date

import pytest

from lclang.utils.calendar import (
    ALL_DAYS,
    DayType,
    at,
    nth_day_of_month,
)


@pytest.mark.asyncio
async def test_transformation_truth_tables_and_canonical_representations() -> None:
    """Composition follows three-state precedence and canonicalizes sets."""
    monday = date(2024, 1, 1)
    tuesday = date(2024, 1, 2)
    sparse = at(monday)
    holiday = nth_day_of_month(2)
    union = holiday + sparse
    assert repr(sparse + holiday) == repr(union)
    assert await union.get_day_type(monday) is DayType.BusinessDay
    assert await union.get_day_type(tuesday) is DayType.BusinessDay
    intersection = sparse & holiday
    assert await intersection.get_day_type(monday) is DayType.Holiday
    assert await intersection.get_day_type(tuesday) is DayType.BusinessDay
    subtraction = ALL_DAYS - holiday
    assert await subtraction.get_day_type(tuesday) is DayType.Holiday
    assert await (sparse >> holiday).get_day_type(tuesday) is DayType.BusinessDay
    assert await (~holiday).get_day_type(tuesday) is DayType.Holiday
    assert ~~holiday is holiday
    assert sparse.business_days() is sparse
    assert holiday.business_days() is holiday
    assert await holiday.holidays().get_day_type(monday) is DayType.Holiday
