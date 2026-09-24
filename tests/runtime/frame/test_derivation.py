"""Behavioural tests for :mod:`lclang.runtime.frame.derivation`."""

from typing import Any, cast

import pytest

import lclang


@pytest.mark.asyncio
async def test_derive_creates_a_detached_independent_child() -> None:
    """Sunny: the child borrows its parent and owns values, cache, and close."""
    module = lclang.define_module("child", {"answer": "base + offset"})
    values: dict[str, object] = {"offset": 2}

    async with lclang.define_frame(lclang.define_module("parent", {"base": "40"})) as parent:
        async with parent.derive(module, values) as child:
            values["offset"] = 100

            assert child.parent is parent
            assert child.module is module
            assert child.frame_id == "child"
            assert child.values == {"offset": 2}
            assert await child.get("answer") == 42
        assert child.closed is True
        assert parent.closed is False
        assert await parent.get("base") == 40
    assert parent.closed is True


@pytest.mark.asyncio
async def test_nested_derive_uses_normal_recursive_shadowing() -> None:
    """Composite: each derived layer participates in nearest-binding lookup."""
    async with lclang.define_frame(
        lclang.define_module("root", {"base": "10", "shared": "1"})
    ) as root:
        async with root.derive(
            lclang.define_module("middle", {"subtotal": "base + shared"}),
            {"shared": 2},
        ) as middle:
            async with middle.derive(
                lclang.define_module(
                    "leaf",
                    {"shared": "3", "total": "subtotal + shared"},
                )
            ) as leaf:
                assert await middle.get("subtotal") == 12
                assert await leaf.get("total") == 15
                assert leaf.get_definition("subtotal") is middle.module.definitions["subtotal"]
            assert leaf.closed is True
        assert middle.closed is True
    assert root.closed is True


@pytest.mark.asyncio
async def test_derive_default_values_are_empty_and_independent() -> None:
    """The shared default object is never retained as mutable Frame state."""
    async with (
        lclang.define_frame() as parent,
        parent.derive(lclang.define_module("first", {})) as first,
        parent.derive(lclang.define_module("second", {})) as second,
    ):
        assert first.values == second.values == {}
        assert first.values is not second.values


@pytest.mark.parametrize(
    ("module", "values", "error"),
    [
        (object(), {}, TypeError),
        (lclang.define_module("child", {}), [], TypeError),
        (lclang.define_module("child", {}), {"": 1}, ValueError),
    ],
)
@pytest.mark.asyncio
async def test_derive_rejects_invalid_inputs(
    module: object,
    values: object,
    error: type[Exception],
) -> None:
    """Rainy: invalid child inputs fail before a usable Frame is returned."""
    async with lclang.define_frame() as parent:
        with pytest.raises(error):
            parent.derive(cast(Any, module), cast(Any, values))
