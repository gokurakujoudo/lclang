"""Unit tests mirroring :mod:`lclang.runtime.frame.limits`."""

import asyncio

import pytest

from lclang.errors import LclEvaluationError
from lclang.lang.parser import parse_expression
from lclang.runtime import EvaluationLimits, Frame, Module
from lclang.types import FrameId, ModuleName


def _frame(
    source: str,
    limits: EvaluationLimits,
    **values: object,
) -> Frame:
    module = Module(ModuleName("app"), {"value": parse_expression(source)})
    return Frame(module, FrameId("frame:1"), values=values, limits=limits)


def test_limit_defaults_are_immutable_and_explicit() -> None:
    """The public value exposes stable conservative defaults."""
    limits = EvaluationLimits()
    assert limits.max_depth == 100
    assert limits.max_steps == 100_000
    assert limits.max_collection_items == 10_000
    with pytest.raises(AttributeError):
        limits.max_depth = 1  # type: ignore[misc]


@pytest.mark.parametrize("invalid", [True, 0, -1])
def test_each_limit_requires_a_positive_non_boolean_integer(invalid: object) -> None:
    """All three budget dimensions reject ambiguous or non-positive values."""
    with pytest.raises(ValueError):
        EvaluationLimits(max_depth=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EvaluationLimits(max_steps=invalid)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EvaluationLimits(max_collection_items=invalid)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "limits", "message"),
    [
        ("-----1", EvaluationLimits(max_depth=3), "depth limit"),
        ("1 + 2 + 3", EvaluationLimits(max_steps=4), "step limit"),
        ("[1, 2, 3]", EvaluationLimits(max_collection_items=2), "collection item limit"),
        ("{a=1, b=2, c=3}", EvaluationLimits(max_collection_items=2), "collection item limit"),
        (
            "[item for item in values]",
            EvaluationLimits(max_collection_items=2),
            "collection item limit",
        ),
    ],
)
async def test_frame_enforces_each_budget(
    source: str,
    limits: EvaluationLimits,
    message: str,
) -> None:
    """Depth, work, displays, and comprehensions fail structurally."""
    frame = _frame(source, limits, values=(1, 2, 3))
    with pytest.raises(LclEvaluationError, match=message) as caught:
        await frame.get("value")
    assert caught.value.span is not None


@pytest.mark.asyncio
async def test_dependency_frames_share_the_active_root_budget() -> None:
    """A parent owner consumes the child's active evaluation allowance."""
    limits = EvaluationLimits(max_steps=5)
    parent = _frame("1 + 2", limits)
    child_module = Module(ModuleName("child"), {"answer": parse_expression("value + 1")})
    child = Frame(child_module, FrameId("child:1"), parent=parent, limits=limits)
    with pytest.raises(LclEvaluationError, match="step limit"):
        await child.get("answer")


@pytest.mark.asyncio
async def test_cached_lookup_consumes_no_new_budget() -> None:
    """A completed snapshot returns without entering evaluator hooks again."""
    calls = 0

    def work() -> int:
        nonlocal calls
        calls += 1
        return 42

    frame = _frame("work()", EvaluationLimits(max_steps=2), work=work)
    assert await frame.get("value") == 42
    assert await frame.get("value") == 42
    assert calls == 1


@pytest.mark.asyncio
async def test_collection_at_limit_is_accepted() -> None:
    """The collection ceiling is inclusive rather than off by one."""
    frame = _frame("[1, 2, 3]", EvaluationLimits(max_collection_items=3))
    assert await frame.get("value") == [1, 2, 3]


@pytest.mark.asyncio
async def test_recalculation_receives_a_fresh_isolated_budget() -> None:
    """Each explicit refresh can spend the full configured allowance."""
    frame = _frame("1 + 2", EvaluationLimits(max_steps=3))
    assert await frame.get("value") == 3
    assert await frame.recalculate("value") == 3


@pytest.mark.asyncio
async def test_independent_owner_tasks_do_not_share_step_counts() -> None:
    """Concurrent roots each receive their own mutable budget state."""
    limits = EvaluationLimits(max_steps=3)
    first = _frame("1 + 2", limits)
    second = _frame("3 + 4", limits)
    results = await asyncio.gather(first.get("value"), second.get("value"))
    assert results[0] == 3
    assert results[1] == 7
