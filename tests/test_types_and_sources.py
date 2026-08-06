"""Behavioural tests for public identifiers and source locations."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from pylcl.source import SourceOrigin, SourcePosition, SourceSpan
from pylcl.types import FrameId, ModuleName, SourceName, VarName
from pylcl.version import LCL_V1, LanguageVersion


def test_identifier_newtypes_preserve_strings_at_runtime() -> None:
    """Nominal identifier types must remain ergonomic string values at runtime."""
    assert VarName("answer") == "answer"
    assert ModuleName("module") == "module"
    assert FrameId("frame:1") == "frame:1"
    assert SourceName("memory") == "memory"


def test_language_v1_is_the_stable_default_constant() -> None:
    """The first public grammar version must have stable serialized value 1."""
    assert LCL_V1 is LanguageVersion.V1
    assert LCL_V1.value == "1"


def test_source_values_are_structural_and_immutable() -> None:
    """Origins, positions, and spans must be safe immutable value objects."""
    origin = SourceOrigin(SourceName("example.lcl"), Path("C:/example.lcl"))
    start = SourcePosition(line=1, column=2, offset=1)
    end = SourcePosition(line=1, column=5, offset=4)
    span = SourceSpan(origin=origin, start=start, end=end)

    assert span == SourceSpan(origin=origin, start=start, end=end)
    with pytest.raises(FrozenInstanceError):
        start.line = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("line", "column", "offset"),
    [(0, 1, 0), (1, 0, 0), (1, 1, -1)],
)
def test_source_position_rejects_invalid_coordinates(
    line: int,
    column: int,
    offset: int,
) -> None:
    """Coordinates must use positive lines/columns and non-negative offsets."""
    with pytest.raises(ValueError):
        SourcePosition(line=line, column=column, offset=offset)


def test_source_span_rejects_reversed_range() -> None:
    """A half-open source range cannot end before its start."""
    origin = SourceOrigin(SourceName("memory"))
    start = SourcePosition(line=2, column=1, offset=5)
    end = SourcePosition(line=1, column=1, offset=4)
    with pytest.raises(ValueError):
        SourceSpan(origin=origin, start=start, end=end)
