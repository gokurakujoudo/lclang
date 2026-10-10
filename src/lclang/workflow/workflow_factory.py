"""Concise validated workflow-definition factories.

Defines ``define_context_task``, ``define_task``, ``define_workflow``,
``validate_workflow_tree``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager
from typing import cast

from lclang.error import LclWorkflowError, WorkflowErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.workflow.definition_validation import (
    require_task_id,
    require_title,
    validate_annotations,
    validate_callable,
)
from lclang.workflow.execution_context import TaskContext
from lclang.workflow.mappings import mapping_variables, require_mapping
from lclang.workflow.status_manager import ExecutionStatusManager
from lclang.workflow.task_id import TaskID
from lclang.workflow.workflow_definition import ContextTask, TaskAction, TaskNode, Workflow


@guard_failure(LclWorkflowError, WorkflowErrorCode.E11_WORKFLOW_FACTORY_NATIVE_FAILURE)
def define_context_task[ArgsT, OutputsT](
    task_id: str,
    title: str,
    task_context: Callable[
        [TaskContext, ArgsT, ExecutionStatusManager],
        AbstractAsyncContextManager[OutputsT],
    ],
    args_mapping: ArgsT,
    outputs_mapping: OutputsT | None = None,
) -> ContextTask:
    """Define one ordered task context.

    :param task_id: Globally unique context-task identifier.
    :param title: Human-readable title.
    :param task_context: Async context-manager factory.
    :param args_mapping: Dataclass argument mapping or exactly typed record variable quote.
    :param outputs_mapping: Optional field mapping or exactly typed whole-resource quote.
    :returns: Immutable context-task definition.
    """
    require_mapping(args_mapping, "context argument mapping")
    if outputs_mapping is not None:
        require_mapping(outputs_mapping, "context output mapping")
    validate_callable(task_context, coroutine=False)
    validate_annotations(task_context, args_mapping, outputs_mapping, context=True)
    return ContextTask(
        require_task_id(task_id),
        require_title(title, "context-task title"),
        cast(Callable[..., object], task_context),
        args_mapping,
        outputs_mapping,
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E11_WORKFLOW_FACTORY_NATIVE_FAILURE)
def define_task[ArgsT, OutputsT](
    task_id: str,
    title: str,
    *,
    task_action: (
        Callable[[TaskContext, ArgsT, ExecutionStatusManager], Awaitable[OutputsT]] | None
    ) = None,
    args_mapping: ArgsT | None = None,
    outputs_mapping: OutputsT | None = None,
    context_tasks: Iterable[ContextTask] = (),
    children: Iterable[TaskNode] = (),
) -> TaskNode:
    """Define one immutable action or structural task node.

    :param task_id: Globally unique task identifier.
    :param title: Human-readable title.
    :param task_action: Optional async task action.
    :param args_mapping: Dataclass mapping or exactly typed record quote for an action.
    :param outputs_mapping: Optional field mapping or exactly typed whole-output quote.
    :param context_tasks: Ordered task contexts.
    :param children: Ordered child task nodes.
    :returns: Immutable task definition.
    :raises LclValidationError: If the callable or declaration containers are invalid.
    :raises LclValidationError: If action/mapping presence is inconsistent.
    """
    if task_action is None:
        if args_mapping is not None or outputs_mapping is not None:
            raise LclValidationError(
                "structural task cannot define action mappings",
                code=WorkflowErrorCode.E11_STRUCTURAL_TASK_CANNOT_DEFINE_ACTION_MAPPINGS,
            )
    else:
        if args_mapping is None:
            raise LclValidationError(
                "task argument mapping is required with an action",
                code=WorkflowErrorCode.E11_TASK_ARGUMENT_MAPPING_IS_REQUIRED_WITH_AN_ACTION,
            )
        require_mapping(args_mapping, "task argument mapping")
        if outputs_mapping is not None:
            require_mapping(outputs_mapping, "task output mapping")
        validate_callable(task_action, coroutine=True)
        validate_annotations(task_action, args_mapping, outputs_mapping)
    contexts = tuple(context_tasks)
    child_nodes = tuple(children)
    if any(not isinstance(item, ContextTask) for item in contexts):
        raise LclValidationError(
            "context tasks must contain ContextTask values",
            code=WorkflowErrorCode.E11_CONTEXT_TASKS_MUST_CONTAIN_CONTEXTTASK_VALUES,
        )
    if any(not isinstance(item, TaskNode) for item in child_nodes):
        raise LclValidationError(
            "children must contain TaskNode values",
            code=WorkflowErrorCode.E11_CHILDREN_MUST_CONTAIN_TASKNODE_VALUES,
        )
    return TaskNode(
        require_task_id(task_id),
        require_title(title, "task title"),
        None if task_action is None else cast(TaskAction, task_action),
        args_mapping,
        outputs_mapping,
        contexts,
        child_nodes,
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E11_WORKFLOW_FACTORY_NATIVE_FAILURE)
def define_workflow(
    title: str,
    root_task: TaskNode,
    lcl_mixin: dict[str, object] | None = None,
) -> Workflow:
    """Define and validate one reusable workflow tree.

    :param title: Human-readable workflow title.
    :param root_task: Root task node.
    :param lcl_mixin: Optional shallow host bindings for configuration and tasks.
    :returns: Immutable validated workflow.
    :raises LclValidationError: If *root_task* has the wrong public type.
    :raises LclValidationError: If IDs or variable declarations conflict.
    """
    if not isinstance(root_task, TaskNode):
        raise LclValidationError(
            "workflow root must be a TaskNode",
            code=WorkflowErrorCode.E11_WORKFLOW_ROOT_MUST_BE_A_TASKNODE,
        )
    validate_workflow_tree(root_task)
    return Workflow(
        require_title(title, "workflow title"), root_task, {} if lcl_mixin is None else lcl_mixin
    )


@guard_failure(LclValidationError, WorkflowErrorCode.E11_WORKFLOW_FACTORY_NATIVE_FAILURE)
def validate_workflow_tree(root: TaskNode) -> None:
    """Reject duplicate IDs and conflicting variable declarations.

    :param root: Root task to inspect depth-first.
    :raises LclValidationError: If an identifier or variable declaration conflicts.
    """
    identifiers: set[TaskID] = set()
    variables: dict[str, object] = {}
    active: set[int] = set()

    def visit(node: TaskNode) -> None:
        """Visit one task and descendants.

        :param node: Current task node.
        :raises LclValidationError: If the active traversal contains a cycle.
        """
        if id(node) in active:
            raise LclValidationError(
                "workflow task cycle detected",
                code=WorkflowErrorCode.E11_WORKFLOW_TASK_CYCLE_DETECTED,
            )
        active.add(id(node))
        declarations: list[tuple[TaskID, object | None, object | None]] = [
            (node.task_id, node.args_mapping, node.outputs_mapping)
        ]
        declarations.extend(
            (item.task_id, item.args_mapping, item.outputs_mapping) for item in node.context_tasks
        )
        for identifier, args, outputs in declarations:
            if identifier in identifiers:
                raise LclValidationError(
                    f"duplicate workflow task ID: {identifier}",
                    code=WorkflowErrorCode.E11_DUPLICATE_WORKFLOW_TASK_ID,
                )
            identifiers.add(identifier)
            for variable in (*mapping_variables(args), *mapping_variables(outputs)):
                previous = variables.setdefault(variable.name, variable)
                if previous is not variable:
                    raise LclValidationError(
                        f"duplicate workflow variable declaration: {variable.name}",
                        code=WorkflowErrorCode.E11_DUPLICATE_WORKFLOW_VARIABLE_DECLARATION,
                    )
        for child in node.children:
            visit(child)
        active.remove(id(node))

    visit(root)
