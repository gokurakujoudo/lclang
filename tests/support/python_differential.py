"""Deterministic Python 3.14 oracles for the shared LCL expression subset."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DifferentialCase:
    """Pair one LCL expression with an explicit Python value oracle.

    :param name: Stable parametrized-test identifier.
    :param source: LCL source in the Python-compatible subset.
    :param resolver: Host values visible to LCL evaluation.
    :param oracle: Explicit Python callable returning the expected value.
    """

    name: str
    source: str
    resolver: Mapping[str, object]
    oracle: Callable[[], object]


@dataclass(frozen=True, slots=True)
class FailureCase:
    """Pair one failing LCL expression with its Python exception oracle.

    :param name: Stable parametrized-test identifier.
    :param source: LCL source in the Python-compatible subset.
    :param resolver: Host values visible to LCL evaluation.
    :param oracle: Explicit Python callable that raises.
    :param python_error: Expected Python cause category.
    """

    name: str
    source: str
    resolver: Mapping[str, object]
    oracle: Callable[[], object]
    python_error: type[Exception]


def python_division_failure() -> object:
    """Raise Python's division-by-zero failure.

    :returns: No value because division fails.
    :raises ZeroDivisionError: Always.
    """
    return 1 / 0


def python_index_failure() -> object:
    """Raise Python's missing-list-index failure.

    :returns: No value because indexing fails.
    :raises IndexError: Always.
    """
    return [1][9]


def python_call_failure() -> object:
    """Raise Python's non-callable invocation failure.

    :returns: No value because the selected integer is not callable.
    :raises TypeError: Always.
    """
    value = 1
    return value()  # type: ignore[operator]


def python_comparison_chain() -> bool:
    """Evaluate a non-constant Python comparison chain.

    :returns: Whether ascending values satisfy the shared operators.
    """
    values = list(range(1, 5))
    return values[0] < values[1] < values[2] != values[3]


# Successful cases intentionally exclude LCL-only null-safe and expression forms.
DIFFERENTIAL_CASES = (
    DifferentialCase("numeric-precedence", "1 + 2 * 3 ** 2", {}, lambda: 1 + 2 * 3**2),
    DifferentialCase("unary-power", "-2 ** 3", {}, lambda: -(2**3)),
    DifferentialCase(
        "text-and-bytes", '("ab" * 2, b"A" + b"B")', {}, lambda: ("ab" * 2, b"A" + b"B")
    ),
    DifferentialCase("comparison-chain", "1 < 2 < 3 != 4", {}, python_comparison_chain),
    DifferentialCase(
        "boolean-values",
        "zero or value and other",
        {"zero": 0, "value": 5, "other": 8},
        lambda: 0 or 5 and 8,
    ),
    DifferentialCase(
        "conditional", "10 if enabled else 20", {"enabled": False}, lambda: 10 if False else 20
    ),
    DifferentialCase("list-unpack", "[1, *items, 4]", {"items": [2, 3]}, lambda: [1, *[2, 3], 4]),
    DifferentialCase(
        "dict-unpack", '{"a": 1, **extra}', {"extra": {"b": 2}}, lambda: {"a": 1, **{"b": 2}}
    ),
    DifferentialCase(
        "slice", "values[1:6:2]", {"values": tuple(range(8))}, lambda: tuple(range(8))[1:6:2]
    ),
    DifferentialCase("call", "choose(3, 8)", {"choose": max}, lambda: max(3, 8)),
    DifferentialCase("format", 'f"{value!r:>6}"', {"value": "x"}, lambda: f"{'x'!r:>6}"),
    DifferentialCase(
        "comprehension",
        "[item * 2 for item in values if item % 2]",
        {"values": range(6)},
        lambda: [item * 2 for item in range(6) if item % 2],
    ),
    DifferentialCase(
        "composite",
        "[text(item)[1:] for item in values if item % 2]",
        {"text": str, "values": range(6)},
        lambda: [str(item)[1:] for item in range(6) if item % 2],
    ),
)

# Failures compare the structured LCL wrapper's underlying Python cause.
FAILURE_CASES = (
    FailureCase("division", "1 / zero", {"zero": 0}, python_division_failure, ZeroDivisionError),
    FailureCase("subscription", "values[9]", {"values": [1]}, python_index_failure, IndexError),
    FailureCase("call", "value()", {"value": 1}, python_call_failure, TypeError),
)
