"""Unit tests mirroring :mod:`lclang.runtime.frame.evaluation_flights`."""

import asyncio

import pytest

from lclang.errors import LclCircularDependencyError, LclEvaluationError
from lclang.lang.parser import parse_expression
from lclang.runtime import Frame, Module
from lclang.types import FrameId, ModuleName


@pytest.mark.asyncio
async def test_concurrent_success_uses_one_owner_task() -> None:
    """Simultaneous lookups share one evaluation and result identity."""
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0
    marker = object()

    async def work() -> object:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return marker

    module = Module(ModuleName("app"), {"value": parse_expression("work()")})
    frame = Frame(module, FrameId("frame:1"), values={"work": work})
    waiters = [asyncio.create_task(frame.get("value")) for _ in range(8)]
    await started.wait()
    release.set()
    results = await asyncio.gather(*waiters)
    assert all(result is marker for result in results)
    assert calls == 1


@pytest.mark.asyncio
async def test_concurrent_failure_shares_cached_exception() -> None:
    """One owner failure is delivered by identity to every waiter."""
    calls = 0

    async def fail() -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        raise ValueError("broken")

    module = Module(ModuleName("app"), {"value": parse_expression("fail()")})
    frame = Frame(module, FrameId("frame:1"), values={"fail": fail})
    outcomes = await asyncio.gather(
        *(frame.get("value") for _ in range(8)),
        return_exceptions=True,
    )
    first = outcomes[0]
    assert isinstance(first, LclEvaluationError)
    assert all(outcome is first for outcome in outcomes)
    assert calls == 1


@pytest.mark.asyncio
async def test_direct_cycle_is_structured_and_cached() -> None:
    """A self-reference fails before awaiting its own in-flight owner."""
    module = Module(ModuleName("app"), {"value": parse_expression("value")})
    frame = Frame(module, FrameId("frame:1"))
    with pytest.raises(LclCircularDependencyError) as first:
        await frame.get("value")
    with pytest.raises(LclCircularDependencyError) as second:
        await frame.get("value")
    assert first.value is second.value
    assert "value -> value" in first.value.message


@pytest.mark.asyncio
async def test_indirect_cycle_reports_ordered_path() -> None:
    """Multi-definition cycles identify the complete dependency route."""
    module = Module(
        ModuleName("app"),
        {"alpha": parse_expression("beta"), "beta": parse_expression("alpha")},
    )
    frame = Frame(module, FrameId("frame:1"))
    with pytest.raises(LclCircularDependencyError) as caught:
        await frame.get("alpha")
    assert "alpha -> beta -> alpha" in caught.value.message
    assert caught.value.span == module.definitions["beta"].span


@pytest.mark.asyncio
async def test_nested_failure_reports_direct_to_failing_variable_stack() -> None:
    """A cached failure retains the complete first evaluation owner path."""
    module = Module(
        ModuleName("diagnostics"),
        {
            "RESULT": parse_expression("middle"),
            "middle": parse_expression("failing"),
            "failing": parse_expression("1 / 0"),
        },
    )
    frame = Frame(module)

    with pytest.raises(LclEvaluationError) as first:
        await frame.get("RESULT")
    with pytest.raises(LclEvaluationError) as second:
        await frame.get("RESULT")

    assert first.value is second.value
    assert first.value.variable_stack == ("RESULT", "middle", "failing")
    assert str(first.value).endswith("[variable evaluation stack: RESULT -> middle -> failing]")


@pytest.mark.asyncio
async def test_concurrent_failures_keep_independent_variable_stacks() -> None:
    """Parallel owner tasks cannot leak their diagnostic paths to each other."""

    async def fail(label: str) -> None:
        await asyncio.sleep(0)
        raise ValueError(label)

    module = Module(
        ModuleName("concurrent-errors"),
        {
            "left": parse_expression("fail('left')"),
            "right": parse_expression("fail('right')"),
        },
    )
    frame = Frame(module, values={"fail": fail})
    outcomes = await asyncio.gather(
        frame.get("left"),
        frame.get("right"),
        return_exceptions=True,
    )

    assert all(isinstance(item, LclEvaluationError) for item in outcomes)
    assert [item.variable_stack for item in outcomes if isinstance(item, LclEvaluationError)] == [
        ("left",),
        ("right",),
    ]
