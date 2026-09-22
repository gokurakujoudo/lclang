"""Workflow defaults share runtime and CLI semantics without shared run state."""

import asyncio
from dataclasses import dataclass, field
from typing import cast

import pytest

import lclang
import lclang.workflow as wf
from tests.workflow.default_support import Value, echo, execution_context, workflow_for


@pytest.mark.asyncio
async def test_default_is_visible_to_lcl_and_is_below_explicit_bindings() -> None:
    """LCL and dataclass mappings resolve one common default binding."""
    value = wf.define_variable[object]("value", default=3)
    calculated = wf.define_variable[object]("calculated")
    workflow = wf.define_workflow("Default", wf.define_task(
        "root", "Root", task_action=echo, args_mapping=Value(value.quote), children=[
            wf.define_task(
                "child", "Child", task_action=echo, args_mapping=Value(calculated.quote),
            ),
        ],
    ))
    for explicit, expected in [({}, 3), ({"value": 8}, 8)]:
        async with lclang.define_frame(
            lclang.define_module("config", {"calculated": "value * 2"}), preset=dict(explicit),
        ) as frame:
            parent = frame.parent
            result = await workflow.execute(execution_context(frame))
            assert result.task_outputs[wf.TaskID("root")] == Value(expected)
            assert result.task_outputs[wf.TaskID("child")] == Value(expected * 2)
            assert frame.parent is parent


@pytest.mark.asyncio
async def test_factory_is_lazy_and_independent_between_runs() -> None:
    """One factory result is shared within a run and never stored in the definition."""
    calls: list[list[int]] = []

    async def factory() -> list[int]:
        await asyncio.sleep(0)
        value: list[int] = []
        calls.append(value)
        return value

    variable = wf.define_variable[object]("value", default_factory=factory)
    workflow = wf.define_workflow("Factory", wf.define_task(
        "root", "Root", task_action=echo, args_mapping=Value(variable.quote), children=[
            wf.define_task("child", "Child", task_action=echo, args_mapping=Value(variable.quote)),
        ],
    ))
    command = workflow.to_cli("run", "Run")
    assert not command.parameter_docs[0].required
    assert not calls
    for _ in range(2):
        async with lclang.define_frame() as frame:
            result = await workflow.execute(execution_context(frame))
            root = cast(Value, result.task_args[wf.TaskID("root")])
            child = cast(Value, result.task_args[wf.TaskID("child")])
            assert root.value is child.value is calls[-1]
    assert len(calls) == 2 and calls[0] is not calls[1]


@pytest.mark.asyncio
async def test_none_identity_field_fallback_and_failed_definition() -> None:
    """Only absence triggers fallback; explicit nulls and objects retain identity."""
    values: tuple[object, ...] = (None, [])
    for value in values:
        workflow = workflow_for(wf.define_variable[object]("value", default=value))
        async with lclang.define_frame() as frame:
            result = await workflow.execute(execution_context(frame))
            assert cast(Value, result.task_args[wf.TaskID("root")]).value is value
            assert not frame.has("value")
    variable = wf.define_variable[object]("value")
    workflow = workflow_for(variable)
    assert not workflow.to_cli("run", "Run").parameter_docs[0].required
    async with lclang.define_frame() as frame:
        result = await workflow.execute(execution_context(frame))
        assert result.task_args[wf.TaskID("root")] == Value()
    workflow = workflow_for(wf.define_variable[object]("value", default=99))
    async with lclang.define_frame(lclang.define_module("bad", {"value": "missing + 1"})) as frame:
        result = await workflow.execute(execution_context(frame))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR
        assert not result.task_args


@pytest.mark.asyncio
async def test_field_factory_and_required_occurrences() -> None:
    """Constructor factories apply per mapping; one required occurrence keeps CLI required."""
    @dataclass
    class Collection:
        value: object = field(default_factory=list)

    @dataclass
    class Required:
        value: object

    from lclang.workflow.mappings import materialize_args

    variable = wf.define_variable[object]("value")
    async with lclang.define_frame() as frame:
        first = cast(Collection, await materialize_args(Collection(variable.quote), frame))
        second = cast(Collection, await materialize_args(Collection(variable.quote), frame))
        assert first.value == second.value == [] and first.value is not second.value
        with pytest.raises(lclang.LclNameError):
            await materialize_args(Required(variable.quote), frame)


@pytest.mark.asyncio
async def test_concurrent_and_repeated_borrowed_frame_runs_are_isolated() -> None:
    """Direct runs share borrowed Frames without sharing factory caches."""
    calls = 0

    async def factory() -> object:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return object()

    workflow = workflow_for(wf.define_variable[object]("value", default_factory=factory))
    async with lclang.define_frame() as frame:
        results = await asyncio.gather(*(
            workflow.execute(execution_context(frame)) for _ in range(20)
        ))
        results.append(await workflow.execute(execution_context(frame)))
        assert len({id(cast(Value, r.task_args[wf.TaskID("root")]).value) for r in results}) == 21
        assert calls == 21
        assert not frame.has("value")


def test_mutually_exclusive_defaults_and_callable_contract() -> None:
    """Invalid declaration shapes fail before workflow execution."""
    with pytest.raises(TypeError, match="mutually exclusive"):
        wf.define_variable[object]("value", default=None, default_factory=list)
    with pytest.raises(TypeError, match="mutually exclusive"):
        wf.define_variable[object]("value", default_factory=cast(object, 3))  # type: ignore[arg-type]
