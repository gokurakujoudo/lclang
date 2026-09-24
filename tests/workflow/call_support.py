"""Reusable real-action harness for dynamic workflow call contracts."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

import pytest

import lclang
from lclang.runtime import Frame
from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    TaskContext,
    TaskNode,
    Workflow,
    WorkflowExecutionContext,
    WorkflowExecutionResult,
    define_task,
    define_variable,
    define_workflow,
)


@dataclass
class Value:
    """One ordinary task value."""

    value: int


@dataclass
class ParentArgs:
    """Inject a test scenario into a real executing action."""

    callback: Callable[[TaskContext, ExecutionStatusManager], Awaitable[Value]]


async def invoke_parent(
    context: TaskContext,
    args: ParentArgs,
    status_mgr: ExecutionStatusManager,
) -> Value:
    """Run the scenario while the action's active lifetime is valid."""
    return await args.callback(context, status_mgr)


async def run_parent(
    callback: Callable[[TaskContext, ExecutionStatusManager], Awaitable[Value]],
    frame: Frame,
    children: list[TaskNode] | None = None,
) -> WorkflowExecutionResult:
    """Execute one parent using deterministic inherited metadata."""
    root = define_task(
        "parent",
        "Parent",
        task_action=invoke_parent,
        args_mapping=ParentArgs(callback),
        children=children or (),
    )
    return await define_workflow("Parent workflow", root).execute(
        WorkflowExecutionContext(
            True,
            date(2026, 9, 23),
            True,
            logging.getLogger("workflow-call"),
            frame,
        )
    )


def make_child(
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
    *,
    grouped: bool = False,
) -> Workflow:
    """Create a reusable child with explicit input and output bindings."""

    async def execute(
        context: TaskContext,
        args: Value,
        status_mgr: ExecutionStatusManager,
    ) -> Value:
        status_mgr.update(status)
        return Value(args.value + 1)

    node = define_task(
        "child",
        "Child",
        task_action=execute,
        args_mapping=Value(define_variable[int]("input").quote),
        outputs_mapping=Value(define_variable[int]("output").quote),
    )
    root = define_task("group", "Group", children=[node]) if grouped else node
    return define_workflow("Child workflow", root)


def install_call_resource(monkeypatch: pytest.MonkeyPatch, factory: Callable[[], object]) -> None:
    """Give calls a real owned definition to exercise root Frame cleanup."""

    def create() -> Frame:
        frame = lclang.define_frame(lclang.define_module("owned", {"resource": "make()"}))
        frame.mixin({"make": factory})
        return frame

    monkeypatch.setattr("lclang.workflow.calls.define_frame", create)
