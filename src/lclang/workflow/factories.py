"""Concise validated workflow-definition factories."""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager
from typing import cast, get_args, get_origin, get_type_hints

from lclang.scopes import validate_qualified_name
from lclang.types import TaskID
from lclang.workflow.context import FailureCoveringContextTask, TaskContext
from lclang.workflow.definitions import ContextTask, TaskAction, TaskNode, Workflow
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.mappings import mapping_variables, require_mapping
from lclang.workflow.mappings.records import mapping_annotation
from lclang.workflow.variables import TaskVar


def require_task_id(value: str) -> TaskID:
    """Return one unqualified valid LCL task identifier.

    :param value: Candidate identifier.
    :returns: Nominal workflow task identifier.
    :raises ValueError: If the value is qualified or invalid.
    """
    parts = validate_qualified_name(value)
    if len(parts) != 1:
        raise ValueError("workflow task ID must be an unqualified LCL identifier")
    return TaskID(value)


def require_title(value: str, field: str) -> str:
    """Normalize one non-empty human-readable title.

    :param value: Candidate title.
    :param field: Diagnostic field label.
    :returns: Normalized title.
    :raises TypeError: If the value is not text.
    :raises ValueError: If normalized text is empty.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field} must be text")
    result = " ".join(value.split())
    if not result:
        raise ValueError(f"{field} cannot be empty")
    return result


def validate_callable(value: object, *, coroutine: bool) -> None:
    """Validate the common three-parameter workflow callable shape.

    :param value: Candidate action or context factory.
    :param coroutine: Whether the callable itself must be an async function.
    :raises TypeError: If its runtime signature is incompatible.
    """
    if not callable(value) or (coroutine and not inspect.iscoroutinefunction(value)):
        message = "workflow action must be async" if coroutine else "context task must be callable"
        raise TypeError(message)
    parameters = tuple(inspect.signature(value).parameters.values())
    if [item.name for item in parameters] != ["context", "args", "status_mgr"] or any(
        item.default is not inspect.Parameter.empty for item in parameters
    ):
        raise TypeError("workflow callable must accept exactly context, args, status_mgr")


def validate_annotations(
    value: object,
    args_mapping: object,
    outputs_mapping: object | None = None,
    *,
    context: bool = False,
) -> None:
    """Require exact public context, argument, and manager annotations.

    :param value: Callable whose annotations are resolved.
    :param args_mapping: Dataclass mapping selecting the argument type.
    :param outputs_mapping: Optional output mapping, including a whole-record variable.
    :param context: Whether the return annotation describes a context manager.
    :raises TypeError: If annotations cannot be resolved or do not match.
    """
    if isinstance(value, FailureCoveringContextTask):
        target = cast(FailureCoveringContextTask[object, object], value).acquire
    else:
        target = (
            value if inspect.isfunction(value) else getattr(value, "__call__")  # noqa: B004, B009
        )
    try:
        hints = get_type_hints(target)
    except Exception as error:
        raise TypeError("workflow callable annotations cannot be resolved") from error
    if (
        hints.get("context") is not TaskContext
        or hints.get("args") != mapping_annotation(args_mapping)
        or hints.get("status_mgr") is not ExecutionStatusManager
    ):
        raise TypeError("workflow callable annotations do not match its mappings")
    if isinstance(outputs_mapping, TaskVar):
        result_type = hints.get("return")
        if context and get_origin(result_type) in {
            AsyncIterator,
            AsyncGenerator,
            AbstractAsyncContextManager,
        }:
            result_type = get_args(result_type)[0]
        if result_type != outputs_mapping.value_type:
            raise TypeError("workflow output annotations do not match its mapping")


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
    :raises TypeError: If the callable or declaration containers are invalid.
    :raises ValueError: If action/mapping presence is inconsistent.
    """
    if task_action is None:
        if args_mapping is not None or outputs_mapping is not None:
            raise ValueError("structural task cannot define action mappings")
    else:
        if args_mapping is None:
            raise ValueError("task argument mapping is required with an action")
        require_mapping(args_mapping, "task argument mapping")
        if outputs_mapping is not None:
            require_mapping(outputs_mapping, "task output mapping")
        validate_callable(task_action, coroutine=True)
        validate_annotations(task_action, args_mapping, outputs_mapping)
    contexts = tuple(context_tasks)
    child_nodes = tuple(children)
    if any(not isinstance(item, ContextTask) for item in contexts):
        raise TypeError("context tasks must contain ContextTask values")
    if any(not isinstance(item, TaskNode) for item in child_nodes):
        raise TypeError("children must contain TaskNode values")
    return TaskNode(
        require_task_id(task_id),
        require_title(title, "task title"),
        None if task_action is None else cast(TaskAction, task_action),
        args_mapping,
        outputs_mapping,
        contexts,
        child_nodes,
    )


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
    :raises TypeError: If *root_task* has the wrong public type.
    :raises ValueError: If IDs or variable declarations conflict.
    """
    if not isinstance(root_task, TaskNode):
        raise TypeError("workflow root must be a TaskNode")
    validate_workflow_tree(root_task)
    return Workflow(
        require_title(title, "workflow title"), root_task, {} if lcl_mixin is None else lcl_mixin
    )


def validate_workflow_tree(root: TaskNode) -> None:
    """Reject duplicate IDs and conflicting variable declarations.

    :param root: Root task to inspect depth-first.
    :raises ValueError: If an identifier or variable declaration conflicts.
    """
    identifiers: set[TaskID] = set()
    variables: dict[str, object] = {}
    active: set[int] = set()

    def visit(node: TaskNode) -> None:
        """Visit one task and descendants.

        :param node: Current task node.
        :raises ValueError: If the active traversal contains a cycle.
        """
        if id(node) in active:
            raise ValueError("workflow task cycle detected")
        active.add(id(node))
        declarations: list[tuple[TaskID, object | None, object | None]] = [
            (node.task_id, node.args_mapping, node.outputs_mapping)
        ]
        declarations.extend(
            (item.task_id, item.args_mapping, item.outputs_mapping) for item in node.context_tasks
        )
        for identifier, args, outputs in declarations:
            if identifier in identifiers:
                raise ValueError(f"duplicate workflow task ID: {identifier}")
            identifiers.add(identifier)
            for variable in (*mapping_variables(args), *mapping_variables(outputs)):
                previous = variables.setdefault(variable.name, variable)
                if previous is not variable:
                    raise ValueError(f"duplicate workflow variable declaration: {variable.name}")
        for child in node.children:
            visit(child)
        active.remove(id(node))

    visit(root)
