"""Deterministic static rendering for workflow definitions."""

from __future__ import annotations

from lclang.workflow.definitions import ContextTask, TaskNode, Workflow
from lclang.workflow.mappings import mapping_text


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
    lines.append(prefix + connector + task_text(task))
    child_prefix = prefix + ("   " if connector == "└─ " else "│  ")
    if task.context_tasks:
        render_context(task, 0, child_prefix, "└─ ", lines)
        return
    for index, child in enumerate(task.children):
        selected = "└─ " if index == len(task.children) - 1 else "├─ "
        render_task(child, child_prefix, selected, lines)


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
    context = task.context_tasks[index]
    lines.append(prefix + connector + context_text(context, "enter"))
    inner_prefix = prefix + ("   " if connector == "└─ " else "│  ")
    if index + 1 < len(task.context_tasks):
        render_context(task, index + 1, inner_prefix, "├─ ", lines)
    else:
        for child in task.children:
            render_task(child, inner_prefix, "├─ ", lines)
    lines.append(inner_prefix + "└─ " + context_text(context, "exit"))


def render_workflow(workflow: Workflow) -> list[str]:
    """Return deterministic static workflow tree lines.

    :param workflow: Workflow definition to render.
    :returns: Fresh ordered line list.
    """
    lines = [f'Workflow "{workflow.title}"']
    render_task(workflow.root_task, "", "└─ ", lines)
    return lines
