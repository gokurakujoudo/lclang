"""Workflow declaration, mapping, and rendering edge contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

import pytest

import lclang
import lclang.workflow as wf
from lclang.workflow.mappings import mapped_outputs, materialize_args, safe_mapping_repr


@dataclass
class Pair:
    """Two fields used to exercise mapping behavior."""

    first: int
    second: int = 2


async def valid_action(
    context: wf.TaskContext,
    args: Pair,
    status_mgr: wf.ExecutionStatusManager,
) -> Pair:
    """Return the supplied mapping.

    :param context: Current task context.
    :param args: Materialized arguments.
    :param status_mgr: Current status manager.
    :returns: Supplied pair.
    """
    del context, status_mgr
    return args


@asynccontextmanager
async def valid_context(
    context: wf.TaskContext,
    args: Pair,
    status_mgr: wf.ExecutionStatusManager,
) -> AsyncIterator[Pair]:
    """Yield the supplied mapping.

    :param context: Current task context.
    :param args: Materialized arguments.
    :param status_mgr: Current status manager.
    :returns: Iterator yielding the pair.
    """
    del context, status_mgr
    yield args


class CallableContext:
    """Callable-object context fixture for annotation discovery."""

    def __call__(
        self,
        context: wf.TaskContext,
        args: Pair,
        status_mgr: wf.ExecutionStatusManager,
    ) -> AbstractAsyncContextManager[Pair]:
        """Return the normal context fixture.

        :param context: Current task context.
        :param args: Mapping arguments.
        :param status_mgr: Context status manager.
        :returns: Async context-manager scope.
        """
        return valid_context(context, args, status_mgr)


def test_variable_and_scalar_declarations_validate_and_normalize() -> None:
    """Variable metadata, IDs, and titles obey stable LCL-facing rules."""
    variable = wf.define_variable[int]("scope.value", "  useful   value  ")
    assert variable.description == "useful value"
    assert cast(object, variable.quote) is variable
    with pytest.raises(TypeError, match="description"):
        wf.define_variable[int]("value", cast(Any, 1))
    with pytest.raises(TypeError, match="Boolean"):
        wf.define_variable[int]("value", is_masked=cast(Any, 1))
    with pytest.raises(ValueError, match="unqualified"):
        wf.define_task("scope.task", "Task")
    with pytest.raises(TypeError, match="title"):
        wf.define_task("task", cast(Any, 1))
    with pytest.raises(ValueError, match="empty"):
        wf.define_task("task", "  ")


def test_factories_reject_inconsistent_mappings_and_callables() -> None:
    """Malformed callable and container shapes fail during definition."""
    with pytest.raises(ValueError, match="structural"):
        wf.define_task("task", "Task", args_mapping=Pair(1))
    with pytest.raises(ValueError, match="required"):
        wf.define_task("task", "Task", task_action=valid_action)
    with pytest.raises(TypeError, match="dataclass"):
        wf.define_task(
            "task", "Task", task_action=valid_action, args_mapping=cast(Any, 1)
        )
    with pytest.raises(TypeError, match="dataclass"):
        wf.define_task(
            "task",
            "Task",
            task_action=valid_action,
            args_mapping=Pair(1),
            outputs_mapping=cast(Any, 1),
        )

    def sync_action(
        context: wf.TaskContext,
        args: Pair,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Pair:
        del context, status_mgr
        return args

    async def defaulted(
        context: wf.TaskContext,
        args: Pair,
        status_mgr: wf.ExecutionStatusManager | None = None,
    ) -> Pair:
        del context, status_mgr
        return args

    async def wrong_annotations(context: int, args: Pair, status_mgr: int) -> Pair:
        del context, status_mgr
        return args

    async def unresolved(
        context: wf.TaskContext,
        args: Pair,
        status_mgr: wf.ExecutionStatusManager,
    ) -> Pair:
        del context, status_mgr
        return args

    unresolved.__annotations__["context"] = "MissingContext"

    for action, message in (
        (sync_action, "async"),
        (defaulted, "exactly"),
        (wrong_annotations, "annotations"),
        (unresolved, "resolved"),
    ):
        with pytest.raises(TypeError, match=message):
            wf.define_task(
                "task", "Task", task_action=cast(Any, action), args_mapping=Pair(1)
            )

    with pytest.raises(TypeError, match="context task"):
        wf.define_context_task("context", "Context", cast(Any, 1), Pair(1))
    with pytest.raises(TypeError, match="context output"):
        wf.define_context_task(
            "context", "Context", valid_context, Pair(1), cast(Any, Pair)
        )
    assert wf.define_context_task(
        "context", "Context", cast(Any, CallableContext()), Pair(1)
    ).task_id == wf.TaskID("context")
    with pytest.raises(TypeError, match="ContextTask"):
        wf.define_task("task", "Task", context_tasks=cast(Any, [object()]))
    with pytest.raises(TypeError, match="TaskNode"):
        wf.define_task("task", "Task", children=cast(Any, [object()]))


def test_workflow_graph_rejects_wrong_roots_cycles_and_variable_aliases() -> None:
    """Tree-wide identity checks reject ambiguous reusable declarations."""
    with pytest.raises(TypeError, match="root"):
        wf.define_workflow("Workflow", cast(Any, object()))

    first = wf.define_variable[int]("same")
    second = wf.define_variable[int]("same")
    child = wf.define_task(
        "child", "Child", task_action=valid_action, args_mapping=Pair(second.quote)
    )
    root = wf.define_task(
        "root",
        "Root",
        task_action=valid_action,
        args_mapping=Pair(first.quote),
        children=[child],
    )
    with pytest.raises(ValueError, match="variable declaration"):
        wf.define_workflow("Workflow", root)

    cyclic = wf.define_task("cycle", "Cycle")
    object.__setattr__(cyclic, "children", (cyclic,))
    with pytest.raises(ValueError, match="cycle"):
        wf.define_workflow("Workflow", cyclic)


@pytest.mark.asyncio
async def test_mapping_edges_are_explicit_safe_and_bounded() -> None:
    """Output selection rejects ambiguity and rendering contains hostile reprs."""
    target = wf.define_variable[int]("target", is_masked=True)
    assert mapped_outputs(None, Pair(1)) == {}
    with pytest.raises(TypeError, match="mapping dataclass"):
        mapped_outputs(Pair(target.quote), object())
    with pytest.raises(ValueError, match="duplicate"):
        mapped_outputs(Pair(target.quote, target.quote), Pair(1, 2))
    assert mapped_outputs(Pair(1, target.quote), Pair(3, 4)) == {"target!": 4}
    async with lclang.define_frame() as frame:
        assert await materialize_args(Pair(1, 2), frame) == Pair(1, 2)

    class BrokenRepr:
        """Raise from representation for defensive static rendering."""

        def __repr__(self) -> str:
            """Raise the fixture error.

            :returns: No representation.
            :raises RuntimeError: Always.
            """
            raise RuntimeError("no repr")

    assert safe_mapping_repr(BrokenRepr()) == "<repr failed: RuntimeError>"
    assert safe_mapping_repr("a\nb") == "'a\\nb'"
    assert safe_mapping_repr("x" * 300).endswith("...<truncated>")


def test_rendering_handles_plain_siblings_and_nested_contexts() -> None:
    """All connector paths remain deterministic with two context wrappers."""
    first = wf.define_context_task("first", "First", valid_context, Pair(1))
    second = wf.define_context_task("second", "Second", valid_context, Pair(2))
    root = wf.define_task(
        "root",
        "Root",
        context_tasks=[first, second],
        children=[wf.define_task("left", "Left"), wf.define_task("right", "Right")],
    )
    lines = wf.define_workflow("Workflow", root).to_lines()
    assert lines[2].startswith("   └─ enter context first")
    assert lines[3].startswith("      ├─ enter context second")
    assert lines[4].startswith("      │  ├─ task left")
    assert lines[5].startswith("      │  ├─ task right")
    assert lines[-1].startswith("      └─ exit context first")

    plain = wf.define_task(
        "plain",
        "Plain",
        children=[wf.define_task("one", "One"), wf.define_task("two", "Two")],
    )
    plain_lines = wf.define_workflow("Plain workflow", plain).to_lines()
    assert plain_lines[2].startswith("   ├─ task one")
    assert plain_lines[3].startswith("   └─ task two")
