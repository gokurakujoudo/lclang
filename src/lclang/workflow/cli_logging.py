"""Final workflow CLI status-tree and lunch logging."""

from __future__ import annotations

import logging
import random

from lclang.runtime import Frame
from lclang.workflow.logging import status_level
from lclang.workflow.models import ExecutionStatus, ExecutionStatusTree


def status_lines(tree: ExecutionStatusTree) -> list[str]:
    """Render one finalized execution status tree.

    :param tree: Root status node.
    :returns: Deterministic tree-shaped status lines.
    """
    detail = f": {tree.task_description}" if tree.task_description else ""
    lines = [f"[{tree.status.value}] {tree.task_name}{detail}"]

    def visit(node: ExecutionStatusTree, prefix: str, last: bool) -> None:
        """Append one status node recursively.

        :param node: Current status node.
        :param prefix: Existing ancestor indentation.
        :param last: Whether this node is the final sibling.
        """
        connector = "└─ " if last else "├─ "
        description = f": {node.task_description}" if node.task_description else ""
        lines.append(
            f"{prefix}{connector}[{node.status.value}] {node.task_name}{description}"
        )
        child_prefix = prefix + ("   " if last else "│  ")
        for index, child in enumerate(node.sub_tasks):
            visit(child, child_prefix, index == len(node.sub_tasks) - 1)

    for index, child in enumerate(tree.sub_tasks):
        visit(child, "", index == len(tree.sub_tasks) - 1)
    return lines


def log_status_tree(
    logger: logging.Logger,
    tree: ExecutionStatusTree,
    workflow_id: str,
) -> None:
    """Log a finalized tree as one severity-aware multi-line record.

    :param logger: Command logger receiving the tree at execution end.
    :param tree: Finalized status tree.
    :param workflow_id: Dot-connected routed command path.
    """
    message = (
        f"workflow complete: [{workflow_id}] {tree.status.value}:\n"
        + "\n".join(status_lines(tree))
    )
    logger.log(status_level(tree.status), "%s", message)


async def log_lunch_option(
    logger: logging.Logger,
    frame: Frame,
    status: ExecutionStatus,
) -> None:
    """Log an optional configured lunch result without affecting execution.

    :param logger: Command logger receiving an optional lunch record.
    :param frame: Invocation Frame supplying ``lunch.options``.
    :param status: Final workflow status.
    :raises BaseException: If cancellation or process control interrupts the operation.

    Ordinary failures in masking, configuration, random choice or logging are
    isolated together; this easter egg must never change a completed workflow.
    """
    try:
        if frame.is_masked("lunch.options"):
            return
        options = await frame.get("lunch.options", fallback=[])
        if not isinstance(options, list) or not options:
            return
        if any(not isinstance(item, str) for item in options):
            return
        selected = random.choice(options) if status is ExecutionStatus.SUCCESS else "no lunch!"
        logger.info("lunch option: %s", selected)
    except Exception:
        return
