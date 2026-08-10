"""Differential checks against explicit Python 3.14 expression oracles."""

from __future__ import annotations

import pytest

import lclang
from lclang.errors import LclEvaluationError
from tests.support.python_differential import (
    DIFFERENTIAL_CASES,
    FAILURE_CASES,
    DifferentialCase,
    FailureCase,
)


@pytest.mark.parametrize("case", DIFFERENTIAL_CASES, ids=lambda case: case.name)
def test_python_compatible_values_and_canonical_round_trips(case: DifferentialCase) -> None:
    """Shared syntax evaluates like its explicit Python oracle twice."""
    expression = lclang.parse_expression(case.source)
    canonical = lclang.to_source(expression)
    expected = case.oracle()
    assert lclang.evaluate_sync(expression, case.resolver) == expected
    assert lclang.evaluate_sync(canonical, case.resolver) == expected


@pytest.mark.parametrize("case", FAILURE_CASES, ids=lambda case: case.name)
def test_python_failure_categories_remain_structured_causes(case: FailureCase) -> None:
    """Shared operation failures retain their Python exception category."""
    with pytest.raises(case.python_error):
        case.oracle()
    with pytest.raises(LclEvaluationError) as raised:
        lclang.evaluate_sync(case.source, case.resolver)
    assert isinstance(raised.value.__cause__, case.python_error)


def test_short_circuit_side_effects_match_python() -> None:
    """Conditional and Boolean selection invoke only the selected callable."""
    lcl_calls: list[str] = []
    python_calls: list[str] = []

    def lcl_mark(value: str) -> str:
        """Record one LCL-selected branch."""
        lcl_calls.append(value)
        return value

    def python_mark(value: str) -> str:
        """Record one Python-selected branch."""
        python_calls.append(value)
        return value

    lcl_value = lclang.evaluate_sync(
        'mark("left") if enabled and mark("condition") else mark("right")',
        {"enabled": False, "mark": lcl_mark},
    )
    python_enabled = False
    python_value = (
        python_mark("left") if python_enabled and python_mark("condition") else python_mark("right")
    )
    assert (lcl_value, lcl_calls) == (python_value, python_calls)
