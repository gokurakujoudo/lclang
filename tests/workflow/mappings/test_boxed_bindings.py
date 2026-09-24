"""Explicit quote boundaries box and unbox without walking ordinary values."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest

import lclang
from lclang.utils import CallableBox, ValueBox
from lclang.workflow import define_variable
from lclang.workflow.mappings import mapped_outputs, materialize_args
from tests.typing.test_workflow_boxes import OptionalRule


@dataclass
class Inputs:
    """Mix optional callbacks, a callable box and an ordinary shared list."""

    rule: OptionalRule
    convert: CallableBox[[str], int]
    shared: list[object]


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True])
async def test_boxed_bindings_retain_payload_identity_and_publish_raw_values(wrapped: bool) -> None:
    """Each explicit binding is converted once; normal containers remain untouched."""
    rule = define_variable[OptionalRule]("rule", is_masked=True)
    convert = define_variable[CallableBox[[str], int]]("convert")
    shared: list[object] = [ValueBox(3)]
    template = Inputs(rule.quote, convert.quote, shared)
    original = Inputs(OptionalRule(None), CallableBox(int), shared)
    async with lclang.define_frame(
        preset={
            "rule": original.rule if wrapped else None,
            "convert": original.convert if wrapped else int,
        }
    ) as frame:
        result = await materialize_args(template, frame)
        assert isinstance(result, Inputs)
        assert result.rule.value is None and result.convert("17") == 17
        assert result.shared is shared
        if wrapped:
            assert result.rule is original.rule and result.convert is original.convert
        updates = await mapped_outputs(template, result, frame)
        assert updates == {"rule!": None, "convert": int}
        frame.mixin(updates)
        assert await frame.get("convert") is int


@dataclass
class Projected:
    """A projected payload whose schema explicitly declares a wrapper."""

    optional: ValueBox[str | None]


@dataclass
class Destination:
    """Receive one wrapped projection."""

    value: ValueBox[str | None]


@pytest.mark.asyncio
async def test_projection_wraps_only_the_selected_binding() -> None:
    """Scope fields remain raw until the explicitly boxed projection is resolved."""
    source = define_variable[Projected]("source")
    projection = source.field("optional", ValueBox[str | None])
    async with lclang.define_frame(preset={"source.optional": None}) as frame:
        result = await materialize_args(Destination(projection.quote), frame)
        assert result == Destination(ValueBox(None))
        assert await frame.get("source.optional") is None
    record = Projected(ValueBox("kept"))
    async with lclang.define_frame(preset={"source": record}) as frame:
        assert await materialize_args(source.quote, frame) is record
        assert (await mapped_outputs(source.quote, record, frame))["source"] is record


@pytest.mark.asyncio
async def test_wrong_boxes_and_unboxed_outputs_are_rejected() -> None:
    """Nominal wrapper identity prevents accidental double boxing or malformed publication."""
    source = define_variable[OptionalRule]("source")
    async with lclang.define_frame(preset={"source": ValueBox(None)}) as frame:
        with pytest.raises(TypeError, match="incompatible box"):
            await materialize_args(source.quote, frame)
        with pytest.raises(TypeError, match="declared box"):
            await mapped_outputs(source.quote, None, frame)


@pytest.mark.asyncio
async def test_callback_box_preserves_awaitables_and_errors() -> None:
    """Forwarding is synchronous and returns the callback's awaitable unchanged."""

    async def callback(value: int) -> int:
        return value + 1

    pending = callback(4)
    boxed: CallableBox[[], object] = CallableBox(lambda: pending)
    assert boxed() is pending
    assert await pending == 5

    def fail() -> None:
        raise ValueError("callback failed")

    with pytest.raises(ValueError, match="callback failed"):
        CallableBox(fail)()


@pytest.mark.asyncio
async def test_repeated_boxing_is_shallow_and_leaves_ordinary_callbacks_untouched() -> None:
    """A larger conversion loop never clones payloads or transforms ordinary variables."""
    value = define_variable[ValueBox[list[int]]]("value")
    callback = define_variable[Callable[[str], int]]("callback")
    payload = [1, 2]
    async with lclang.define_frame(preset={"value": payload, "callback": int}) as frame:
        for _ in range(1000):
            boxed = await materialize_args(value.quote, frame)
            assert isinstance(boxed, ValueBox) and cast(ValueBox[object], boxed).value is payload
        assert await materialize_args(callback.quote, frame) is int
