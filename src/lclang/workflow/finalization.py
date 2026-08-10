"""Shared locking and deterministic workflow status aggregation."""

from __future__ import annotations

from dataclasses import dataclass, field

from lclang.workflow.models import ExecutionStatus, ExecutionStatusTree, ExecutionTaskType


@dataclass(slots=True)
class SharedExecutionState:
    """Track finalized nodes shared by every manager cursor.

    :param locked_nodes: Identity values of finalized tree nodes.
    """

    locked_nodes: set[int] = field(default_factory=set)


def ensure_unlocked(state: SharedExecutionState, node: ExecutionStatusTree) -> None:
    """Reject a manager operation against one finalized node.

    :param state: Shared lock registry.
    :param node: Current manager node.
    :returns: ``None``.
    :raises RuntimeError: If *node* is finalized.
    """
    if id(node) in state.locked_nodes:
        raise RuntimeError("execution status subtree is already finalized")


def ensure_can_add(state: SharedExecutionState, node: ExecutionStatusTree) -> None:
    """Require an editable composite task before adding a child.

    :param state: Shared lock registry.
    :param node: Current manager node.
    :returns: ``None``.
    :raises RuntimeError: If *node* is finalized.
    :raises ValueError: If *node* is a step.
    """
    ensure_unlocked(state, node)
    if node.task_type is ExecutionTaskType.STEP:
        raise ValueError("a step manager cannot contain sub-tasks")


def finalize_node(state: SharedExecutionState, node: ExecutionStatusTree) -> None:
    """Recursively aggregate one unlocked node and add it to the lock registry.

    :param state: Shared lock registry.
    :param node: Node to finalize; locked descendants are accepted as snapshots.
    :returns: ``None``.
    """
    if id(node) in state.locked_nodes:
        return
    for child in node.sub_tasks:
        finalize_node(state, child)
    if node.status is ExecutionStatus.RUNNING:
        node.status = ExecutionStatus.FAILURE
        node.task_description += " (did not finish)"
    if node.sub_tasks:
        aggregate_children(node)
    state.locked_nodes.add(id(node))


def aggregate_children(node: ExecutionStatusTree) -> None:
    """Apply deterministic child severity and clean-result rules to one task.

    :param node: Composite node whose direct children are finalized.
    :returns: ``None``.
    """
    errors = [child for child in node.sub_tasks if child.status is ExecutionStatus.ERROR]
    if node.status is ExecutionStatus.ERROR:
        return
    if errors:
        node.status = ExecutionStatus.ERROR
        append_child_issue(node, errors[0])
        return
    if node.status is ExecutionStatus.FAILURE:
        return
    failures = [child for child in node.sub_tasks if child.status is ExecutionStatus.FAILURE]
    if failures:
        node.status = ExecutionStatus.FAILURE
        append_child_issue(node, failures[0])
        return
    if any(child.status is ExecutionStatus.PENDING for child in node.sub_tasks):
        node.status = ExecutionStatus.PENDING
        return
    node.status = (
        ExecutionStatus.SKIPPED
        if all(child.status is ExecutionStatus.SKIPPED for child in node.sub_tasks)
        else ExecutionStatus.SUCCESS
    )


def append_child_issue(parent: ExecutionStatusTree, child: ExecutionStatusTree) -> None:
    """Append one direct winning child cause to its parent description.

    :param parent: Parent whose aggregate status was selected by *child*.
    :param child: First direct child with the winning failure severity.
    :returns: ``None``.
    """
    parent.task_description += f" (sub-task '{child.task_name}' ended with {child.status.value})"
