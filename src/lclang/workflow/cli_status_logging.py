"""Final workflow CLI status-tree and lunch logging.

Defines ``status_lines``, ``log_status_tree``, ``log_lunch_option``.
"""

from __future__ import annotations

import logging
import random
from typing import cast

from lclang.error import LclWorkflowError, WorkflowErrorCode
from lclang.error.operation_guard import guard_async_failure, guard_failure
from lclang.lang.runtime import Frame
from lclang.logger import Logger
from lclang.utils.text_tree import TextTree, build_text_tree, render_text_tree
from lclang.workflow.execution_status import ExecutionStatus, ExecutionStatusTree
from lclang.workflow.task_logging import status_level


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def status_lines(tree: ExecutionStatusTree) -> list[str]:
    """Render one finalized execution status tree.

    :param tree: Root status node.
    :returns: Deterministic tree-shaped status lines.
    """

    def visit(node: ExecutionStatusTree) -> TextTree:
        """Detach one status node while preserving recorded execution order.

        :param node: Current status node.
        :returns: Text node with its ordered child snapshots.
        """
        description = f": {node.task_description}" if node.task_description else ""
        return build_text_tree(
            f"[{node.status.value}] {node.task_name}{description}",
            tuple(visit(child) for child in node.sub_tasks),
        )

    return render_text_tree(visit(tree))


@guard_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
def log_status_tree(
    logger: logging.Logger | Logger,
    tree: ExecutionStatusTree,
    workflow_id: str,
) -> None:
    """Log a finalized tree as one severity-aware multi-line record.

    :param logger: Command logger receiving the tree at execution end.
    :param tree: Finalized status tree.
    :param workflow_id: Dot-connected routed command path.
    """
    message = f"workflow complete: [{workflow_id}] {tree.status.value}:\n" + "\n".join(
        status_lines(tree)
    )
    logger.log(status_level(tree.status), "%s", message)


@guard_async_failure(LclWorkflowError, WorkflowErrorCode.E31_TASK_EXECUTION_NATIVE_FAILURE)
async def log_lunch_option(
    logger: logging.Logger | Logger,
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
        if any(not isinstance(item, str) for item in cast(list[object], options)):
            return
        selected = (
            random.choice(cast(list[str], options))
            if status is ExecutionStatus.SUCCESS
            else "no lunch!"
        )
        logger.info("lunch option: %s", selected)
    except Exception:
        return
