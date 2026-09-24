"""Dataclass flattening expands only the selected structural paths."""

from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from lclang.utils import flatten_to_dict


@dataclass
class Leaf:
    """Ordinary shared container leaf."""

    items: list[str] = field(default_factory=list[str])


@dataclass
class Branch:
    """Two separately selectable record branches."""

    a: Leaf = field(default_factory=Leaf)
    b: Leaf = field(default_factory=Leaf)


@dataclass
class Root:
    """One nested record and an ordinary value."""

    branch: Branch = field(default_factory=Branch)
    label: str = "root"


def test_flattening_modes_and_relative_selection() -> None:
    """Ancestors expand only to reach selected targets, never unrelated siblings."""
    value = Root()
    shallow = flatten_to_dict(value, nested=False)
    assert shallow == {"branch": value.branch, "label": "root"}
    assert shallow["branch"] is value.branch
    assert flatten_to_dict(value, nested=set()) == shallow
    full = flatten_to_dict(value, "csv")
    assert full == {"csv.branch.a.items": [], "csv.branch.b.items": [], "csv.label": "root"}
    assert full["csv.branch.a.items"] is value.branch.a.items
    selected = flatten_to_dict(value, "csv", {"branch.a"})
    assert selected == {
        "csv.branch.a.items": [],
        "csv.branch.b": value.branch.b,
        "csv.label": "root",
    }
    assert selected["csv.branch.b"] is value.branch.b
    assert flatten_to_dict(value, nested={"branch"})["branch.a"] is value.branch.a


@pytest.mark.parametrize(
    "path",
    [
        "missing",
        "branch.missing",
        "label",
        "branch.a.items",
        "",
        "a..b",
    ],
)
def test_invalid_selected_paths_fail(path: str) -> None:
    """Typos and scalar targets cannot silently change the requested shape."""
    with pytest.raises(ValueError):
        flatten_to_dict(Root(), nested={path})


def test_invalid_argument_types_fail() -> None:
    """Classes, mappings and malformed expansion controls are not accepted."""
    invalid: tuple[object, ...] = (Root, {}, None)
    for value in invalid:
        with pytest.raises(TypeError):
            flatten_to_dict(value)
    with pytest.raises(TypeError):
        flatten_to_dict(Root(), prefix=cast(Any, 1))
    for nested in (None, ["branch"], {1}):
        with pytest.raises(TypeError):
            flatten_to_dict(Root(), nested=cast(Any, nested))


def test_cycles_shared_records_empty_records_and_class_values() -> None:
    """Only cycles on expanded paths fail; empty records remain meaningful leaves."""

    @dataclass
    class Empty:
        pass

    @dataclass
    class Node:
        child: object

    cyclic = Node(None)
    cyclic.child = cyclic
    with pytest.raises(ValueError, match="cyclic"):
        flatten_to_dict(cyclic)
    assert flatten_to_dict(cyclic, nested=False)["child"] is cyclic
    empty = Empty()
    assert flatten_to_dict(empty) == {}
    assert flatten_to_dict(Node(empty), nested={"child"}) == {"child": empty}
    assert flatten_to_dict(Node(Empty)) == {"child": Empty}
    shared = Leaf()
    assert flatten_to_dict(Branch(shared, shared)) == {"a.items": [], "b.items": []}
