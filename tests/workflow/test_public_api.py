"""Acceptance tests for the workflow status public namespace."""

import lclang.workflow as workflow


def test_workflow_namespace_exports_only_status_contract() -> None:
    """Workflow callers receive the four documented public status types."""
    assert workflow.__all__ == [
        "ExecutionStatus",
        "ExecutionStatusManager",
        "ExecutionStatusStep",
        "ExecutionStatusTree",
        "ExecutionTaskType",
    ]
