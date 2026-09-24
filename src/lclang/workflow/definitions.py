"""Immutable workflow, task, and context-task definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from lclang.types import TaskID

if TYPE_CHECKING:
    from lclang.cli import Command
    from lclang.workflow.context import (
        TaskContext,
        WorkflowExecutionContext,
        WorkflowExecutionResult,
    )
    from lclang.workflow.manager import ExecutionStatusManager

type TaskAction = Callable[..., Awaitable[object]]
type ContextAction = Callable[..., AbstractAsyncContextManager[object]]


@dataclass(frozen=True, slots=True)
class ContextTask:
    """Declare one resource or exception-handling task context.

    :param task_id: Globally unique LCL identifier.
    :param title: Human-readable title.
    :param task_context: Async context-manager factory.
    :param args_mapping: Dataclass argument mapping or whole-record variable quote.
    :param outputs_mapping: Optional dataclass resource mapping or whole-record quote.
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
    :param args_mapping: Dataclass mapping or whole-record quote required for an action.
    :param outputs_mapping: Optional field mapping or whole-record publication quote.
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
    :param lcl_mixin: Shallow host bindings exposed to configuration and tasks.
    """

    title: str
    root_task: TaskNode
    lcl_mixin: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        """Detach host bindings while preserving their values by reference.

        :raises TypeError: If binding names are not strings.
        :raises ValueError: If binding names or scopes conflict.
        """
        from lclang.runtime import Preset

        snapshot = dict(self.lcl_mixin)
        Preset("workflow", snapshot)
        object.__setattr__(self, "lcl_mixin", MappingProxyType(snapshot))

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

    def execute_in_task(
        self,
        context: TaskContext,
        status_mgr: ExecutionStatusManager,
        *,
        name: str,
        preset: Mapping[str, object] | None = None,
    ) -> AbstractAsyncContextManager[WorkflowExecutionResult]:
        """Execute a child workflow in an action-owned asynchronous scope.

        :param context: Active parent action metadata and logger.
        :param status_mgr: Editable parent action status manager.
        :param name: Unique call name under that task.
        :param preset: Explicit bindings copied shallowly into an isolated Frame.
        :returns: Async context yielding the native result while its Frame remains open.
        :raises TypeError: On incompatible input types or invalid preset bindings.
        :raises ValueError: On invalid or conflicting names or a leaf-step parent.
        :raises RuntimeError: Outside an active action or with a finalized parent.
        :raises BaseException: On scope setup, cleanup, body errors or cancellation.
        """
        from lclang.workflow.calls import execute_workflow_in_task

        return execute_workflow_in_task(self, context, status_mgr, name=name, preset=preset)

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
