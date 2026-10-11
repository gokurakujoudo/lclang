"""Deterministic static rendering for workflow definitions.

Defines ``task_text``, ``context_text``, ``render_task``, ``render_context``,
``render_workflow``, ``build_task_display``, ``build_context_display``.
"""

from __future__ import annotations

from lclang.error import LclWorkflowError, WorkflowErrorCode
from lclang.error.operation_guard import guard_failure
from lclang.utils.text_tree import TextTree, render_text_tree
from lclang.workflow.mappings import mapping_text
from lclang.workflow.workflow_definition import ContextTask, TaskNode, Workflow


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def task_text(task: TaskNode) -> str:
    """Render one task definition line.

    :param task: Task node to describe.
    :returns: Stable task text without a tree prefix.
    """
    return (
        f'task {task.task_id} "{task.title}" '
        f"args={mapping_text(task.args_mapping, False)} "
        f"outputs={mapping_text(task.outputs_mapping, True)}"
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def context_text(context: ContextTask, stage: str) -> str:
    """Render one context entry or exit line.

    :param context: Context task to describe.
    :param stage: Literal ``enter`` or ``exit`` stage label.
    :returns: Stable context text without a tree prefix.
    """
    return (
        f'{stage} context {context.task_id} "{context.title}" '
        f"args={mapping_text(context.args_mapping, False)} "
        f"outputs={mapping_text(context.outputs_mapping, True)}"
    )


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def render_task(
    task: TaskNode,
    prefix: str,
    connector: str,
    lines: list[str],
) -> None:
    """Append one task and its statically scoped descendants.

    :param task: Task node to append.
    :param prefix: Existing ancestor indentation.
    :param connector: Current branch connector.
    :param lines: Mutable output line collector.
    """
    lines.extend(render_text_tree(build_task_display(task), prefix=prefix, connector=connector))


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def render_context(
    task: TaskNode,
    index: int,
    prefix: str,
    connector: str,
    lines: list[str],
) -> None:
    """Append one nested context wrapper and its reverse-order exit.

    :param task: Task owning the context sequence and children.
    :param index: Current context index.
    :param prefix: Existing ancestor indentation.
    :param connector: Current branch connector.
    :param lines: Mutable output line collector.
    """
    lines.extend(
        render_text_tree(build_context_display(task, index), prefix=prefix, connector=connector)
    )


def build_task_display(task: TaskNode) -> TextTree:
    """Adapt workflow definitions to shared text connectors in execution order.

    :param task: Static task whose callbacks are never invoked during rendering.
    :returns: Detached task text with scoped contexts or child task definitions.
    """
    children = (
        (build_context_display(task, 0),)
        if task.context_tasks
        else tuple(build_task_display(child) for child in task.children)
    )
    return task_text(task), children


def build_context_display(task: TaskNode, index: int) -> TextTree:
    """Retain forward context entry and reverse context exit in a text tree.

    :param task: Task owning the static context sequence.
    :param index: Current context position within that sequence.
    :returns: Entry node containing nested work and its matching exit leaf.
    """
    context = task.context_tasks[index]
    children = (
        (build_context_display(task, index + 1),)
        if index + 1 < len(task.context_tasks)
        else tuple(build_task_display(child) for child in task.children)
    )
    return context_text(context, "enter"), (*children, (context_text(context, "exit"), ()))


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def render_workflow(workflow: Workflow) -> list[str]:
    """Return deterministic static workflow tree lines.

    :param workflow: Workflow definition to render.
    :returns: Fresh ordered line list.
    """
    lines = [f'Workflow "{workflow.title}"']
    render_task(workflow.root_task, "", "└─ ", lines)
    return lines
