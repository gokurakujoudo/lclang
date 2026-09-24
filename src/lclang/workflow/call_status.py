"""Detached status attachment and monotonic severity for dynamic workflow calls."""

from lclang.workflow.definitions import TaskNode
from lclang.workflow.manager import ExecutionStatusManager
from lclang.workflow.models import ExecutionStatus, ExecutionStatusTree


def copy_status_tree(node: ExecutionStatusTree) -> ExecutionStatusTree:
    """Copy status nodes and child containers without sharing mutable tree state.

    :param node: Completed source subtree.
    :returns: Detached recursive copy retaining scalar descriptions and order.
    """
    return ExecutionStatusTree(
        node.status,
        node.task_type,
        node.task_name,
        node.task_description,
        [copy_status_tree(child) for child in node.sub_tasks],
    )


def attach_call_status(
    manager: ExecutionStatusManager,
    status: ExecutionStatusTree,
    root: TaskNode,
) -> None:
    """Attach completed children while omitting an empty-behavior grouping root.

    :param manager: Editable node representing this dynamic call.
    :param status: Native workflow result, left untouched.
    :param root: Static root definition controlling grouping visibility.
    """
    children = status.sub_tasks
    if root.task_action is None and not root.context_tasks and children:
        children = children[0].sub_tasks
    manager.current.sub_tasks.extend(copy_status_tree(child) for child in children)
    manager.update(status.status, status.task_description)


def propagate_call_status(parent: ExecutionStatusManager, status: ExecutionStatus) -> None:
    """Raise the parent's severity without clearing a previous call's failure.

    :param parent: Editable action status manager.
    :param status: Latest native call outcome.
    """
    if parent.current.status is ExecutionStatus.ERROR:
        return
    if status is ExecutionStatus.ERROR:
        parent.update(ExecutionStatus.ERROR)
    elif status in {ExecutionStatus.FAILURE, ExecutionStatus.FAILURE_COVERED}:
        parent.update(ExecutionStatus.FAILURE)
