"""Behavioural tests for definition-scoped ``lhs()`` lookup."""

import asyncio

import pytest

from lclang.error import LclEvaluationError
from lclang.lang import LCL_ROOT, define_frame, define_module
from lclang.lang.engine.evaluator.definition_scope import definition_scope


@pytest.mark.asyncio
async def test_lhs_tracks_nested_and_calling_definition_names() -> None:
    """Nested evaluation and a deferred closure each see their active owner."""
    module = define_module(
        "owners",
        {
            "k": '{"name": lhs()}',
            "outer": '{"name": lhs(), "nested": k}',
            "owner_function": "() -> lhs()",
            "called": "owner_function()",
        },
    )
    frame = define_frame(module)
    try:
        assert await frame.get("outer") == {
            "name": "outer",
            "nested": {"name": "k"},
        }
        assert await frame.get("called") == "owner_function"
    finally:
        await frame.close()


@pytest.mark.asyncio
async def test_lhs_context_is_isolated_between_concurrent_definitions() -> None:
    """Concurrent owner Tasks retain distinct definition names across awaits."""

    async def delayed(value: str) -> str:
        await asyncio.sleep(0)
        return value

    frame = define_frame(
        define_module("concurrent", {"left": "delayed(lhs())", "right": "delayed(lhs())"}),
        preset={"delayed": delayed},
    )
    try:
        assert list(await asyncio.gather(frame.get("left"), frame.get("right"))) == [
            "left",
            "right",
        ]
    finally:
        await frame.close()


@pytest.mark.asyncio
async def test_lhs_uses_caller_for_arguments_and_lexical_owner_for_function_body() -> None:
    """A nested call separates its argument owner from its closure owner."""
    frame = define_frame(
        define_module(
            "nested-lhs",
            {
                "x": "(a) -> f'{a}-{lhs()}'",
                "y": "x(lhs())",
            },
        )
    )
    try:
        assert await frame.get("y") == "y-x"
    finally:
        await frame.close()


def test_lhs_rejects_calls_outside_frame_definition_evaluation() -> None:
    """The fundamental function cannot invent a name in direct Python use."""
    function = LCL_ROOT.values["lhs"]
    with pytest.raises(LclEvaluationError, match="Frame definition"):
        function()  # type: ignore[operator]


def test_definition_scope_rejects_an_empty_owner_name() -> None:
    """Definition context setup rejects a missing owner deterministically."""
    with pytest.raises(LclEvaluationError, match="cannot be empty"), definition_scope(""):
        pass
