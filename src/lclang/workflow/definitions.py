"""Immutable workflow, task, and context-task definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lclang.types import TaskID

if TYPE_CHECKING:
    from lclang.cli import Command
    from lclang.workflow.context import (
        WorkflowExecutionContext,
        WorkflowExecutionResult,
    )

type TaskAction = Callable[..., Awaitable[object]]
type ContextAction = Callable[..., AbstractAsyncContextManager[object]]


@dataclass(frozen=True, slots=True)
class ContextTask:
    """Declare one resource or exception-handling task context.

    :param task_id: Globally unique LCL identifier.
    :param title: Human-readable title.
    :param task_context: Async context-manager factory.
    :param args_mapping: Dataclass argument mapping.
    :param outputs_mapping: Optional dataclass resource mapping.
    """

    task_id: TaskID
    title: str
    task_context: Callable[..., object]
    args_mapping: object
    outputs_mapping: object | None


@dataclass(frozen=True, slots=True)
class TaskNode:
    """Declare one action and its ordered context and child tasks.

    :param task_id: Globally unique LCL identifier.
    :param title: Human-readable title.
    :param task_action: Optional async action.
    :param args_mapping: Required dataclass mapping for an action.
    :param outputs_mapping: Optional explicit publication mapping.
    :param context_tasks: Ordered context declarations.
    :param children: Ordered child task nodes.
    """

    task_id: TaskID
    title: str
    task_action: TaskAction | None
    args_mapping: object | None
    outputs_mapping: object | None
    context_tasks: tuple[ContextTask, ...]
    children: tuple[TaskNode, ...]


@dataclass(frozen=True, slots=True)
class Workflow:
    """Retain one reusable validated tree-shaped workflow definition.

    :param title: Human-readable workflow title.
    :param root_task: Root task node.
    """

    title: str
    root_task: TaskNode

    async def execute(self, context: WorkflowExecutionContext) -> WorkflowExecutionResult:
        """Execute this definition once against a borrowed Frame.

        :param context: Execution metadata and shared Frame.
        :returns: Final status and materialized action values.
        """
        from lclang.workflow.runner import execute_workflow

        return await execute_workflow(self, context)

    def to_lines(self) -> list[str]:
        """Render the static task and context tree without executing it.

        :returns: Deterministic tree lines with argument and output flows.
        """
        from lclang.workflow.rendering import render_workflow

        return render_workflow(self)

    def to_cli(
        self,
        name: str,
        summary: str,
        preset: dict[str, object] | None = None,
    ) -> Command:
        """Convert this workflow into one typed CLI command.

        :param name: CLI command name.
        :param summary: Human-readable command summary.
        :param preset: Optional external-variable defaults.
        :returns: Executable CLI command.
        """
        from lclang.workflow.cli import workflow_command

        return workflow_command(self, name, summary, preset)
