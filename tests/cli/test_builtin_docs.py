"""Behavioral tests mirroring :mod:`lclang.cli.builtin_docs`."""

from collections.abc import Mapping

import pytest

import lclang.cli.builtin_docs as builtin_docs
from lclang.api import LCL_BUILTIN_VALUES
from lclang.cli.builtin_docs import (
    BUILTIN_DESCRIPTIONS,
    CALENDAR_DESCRIPTIONS,
    NAMESPACE_DESCRIPTIONS,
    ROOT_BUILTIN_DESCRIPTIONS,
    render_builtin_docs,
)
from lclang.stdlib import STANDARD_MANIFESTS
from lclang.utils.calendar.lcl import CALENDARS_NAMESPACE


def test_builtin_docs_render_complete_deterministic_nested_inventory() -> None:
    """Every canonical value appears once with stable nested namespace methods."""
    rendered = render_builtin_docs()
    lines = rendered.splitlines()
    top_names = [line[2:].split(": ", 1)[0] for line in lines if line.startswith("- ")]
    expected_top_names = sorted(
        {
            *LCL_BUILTIN_VALUES,
            *ROOT_BUILTIN_DESCRIPTIONS,
            *(manifest.namespace for manifest in STANDARD_MANIFESTS),
        }
    )
    assert top_names == expected_top_names
    assert len(lines) == (
        len(expected_top_names)
        + sum(len(manifest.entries) for manifest in STANDARD_MANIFESTS)
        + len(CALENDARS_NAMESPACE)
    )
    assert "- abs: Return the absolute value." in lines
    assert "- lhs: Return the active definition name." in lines
    assert "- recursive: Build a variadic eager fixed point." in lines
    iter_index = lines.index(
        "- iter: Synchronous and asynchronous iterable helpers."
    )
    assert lines[iter_index + 1 : iter_index + 3] == [
        "  - collect: Collect sync or async items.",
        "  - first: Return the first item or a default.",
    ]
    assert render_builtin_docs() == rendered


def test_builtin_doc_metadata_exactly_covers_safe_single_line_names() -> None:
    """Description metadata cannot drift, duplicate names, or break line syntax."""
    assert {*BUILTIN_DESCRIPTIONS, *NAMESPACE_DESCRIPTIONS} == set(LCL_BUILTIN_VALUES)
    assert set(ROOT_BUILTIN_DESCRIPTIONS) == {"lhs"}
    assert set(NAMESPACE_DESCRIPTIONS) == {
        *(manifest.namespace for manifest in STANDARD_MANIFESTS),
        "calendars",
    }
    assert set(CALENDAR_DESCRIPTIONS) == set(CALENDARS_NAMESPACE)
    descriptions = (
        *BUILTIN_DESCRIPTIONS.values(),
        *ROOT_BUILTIN_DESCRIPTIONS.values(),
        *NAMESPACE_DESCRIPTIONS.values(),
        *CALENDAR_DESCRIPTIONS.values(),
        *(
            entry.summary
            for manifest in STANDARD_MANIFESTS
            for entry in manifest.entries
        ),
    )
    assert all(value.strip() == value and value for value in descriptions)
    assert all("\n" not in value and "\r" not in value for value in descriptions)
    assert all(not line.endswith(" ") for line in render_builtin_docs().splitlines())


@pytest.mark.parametrize(
    ("target", "replacement", "message"),
    [
        ("BUILTIN_DESCRIPTIONS", {}, "builtin descriptions"),
        ("NAMESPACE_DESCRIPTIONS", {}, "namespace descriptions"),
        ("CALENDAR_DESCRIPTIONS", {}, "calendar descriptions"),
        ("ROOT_BUILTIN_DESCRIPTIONS", {"abs": "Duplicate."}, "must be unique"),
        ("ROOT_BUILTIN_DESCRIPTIONS", {"lhs": " "}, "non-blank and trimmed"),
        ("ROOT_BUILTIN_DESCRIPTIONS", {"lhs": "two\nlines"}, "occupy one line"),
    ],
)
def test_builtin_docs_reject_metadata_drift(
    monkeypatch: pytest.MonkeyPatch,
    target: str,
    replacement: Mapping[str, str],
    message: str,
) -> None:
    """Missing, colliding, blank, and multiline descriptions fail explicitly."""
    monkeypatch.setattr(builtin_docs, target, replacement)
    with pytest.raises(ValueError, match=message):
        builtin_docs.render_builtin_docs()
