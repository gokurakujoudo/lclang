"""Declared record boundaries in recursive workflow mapping logs."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import pytest

from lclang.lang import define_frame, define_module
from lclang.workflow import TaskID, WorkflowExecutionContext, define_variable
from lclang.workflow.task_logging import mapping_message
from tests.workflow.logging_support import Transform


@dataclass
class PlainRecord:
    """A business record whose fields remain visible in nested logs."""

    label: str
    count: int = 2


@dataclass
class Leaf[T]:
    """Supply one specialized field inside a genuine generic record."""

    value: T


@dataclass
class MixedRecords:
    """Combine record annotations with callback and opaque leaf annotations."""

    protocol: Leaf[Transform]
    callable: Leaf[Callable[[str], Awaitable[str]]]
    opaque: Leaf[object]
    arbitrary: Leaf[Any]
    record_class: Leaf[type[PlainRecord]]
    record: Leaf[PlainRecord]
    scalar: Leaf[int]


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [False, True])
async def test_mapping_logs_follow_generic_declarations_and_keep_opaque_values(
    output: bool,
) -> None:
    """Generic records expand while callbacks, opaque values and classes stay leaves."""
    source = define_variable[MixedRecords]("source")
    async with define_frame(
        define_module("callback", {"transform": "(value) -> value.upper()"})
    ) as frame:
        callback = cast(Transform, await frame.get("transform"))
        value = MixedRecords(
            Leaf(callback),
            Leaf(callback),
            Leaf(callback),
            Leaf(callback),
            Leaf(PlainRecord),
            Leaf(PlainRecord("retained")),
            Leaf(7),
        )
        context = WorkflowExecutionContext(
            False, date(2026, 10, 13), True, logging.getLogger("mapping-leaves"), frame
        )
        message = mapping_message(context, (TaskID("root"),), source.quote, value, output=output)
        assert await callback("hello") == "HELLO"
    arrow = "->" if output else "<-"
    for name in ("protocol", "callable", "opaque", "arbitrary"):
        row = next(
            line for line in message.splitlines() if line.strip().startswith(f"{name}.value ")
        )
        assert f"{arrow} [source.{name}]: (LclFunctionValue)" in row
    assert "record.value.label" in message and "(str) 'retained'" in message
    assert "record.value.count" in message and "(int) 2" in message
    assert "record_class.value" in message and "(type)" in message
    assert "record_class.value.label" not in message
    assert "scalar.value" in message and "(int) 7" in message
