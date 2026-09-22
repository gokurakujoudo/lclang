"""Acceptance tests for the workflow status public namespace."""

import lclang.workflow as workflow


def test_workflow_namespace_exports_complete_execution_contract() -> None:
    """Workflow callers receive definitions, execution values, and statuses."""
    assert workflow.__all__ == [
        "ContextTask",
        "ExecutionStatus",
        "ExecutionStatusManager",
        "ExecutionStatusStep",
        "ExecutionStatusTree",
        "ExecutionTaskType",
        "FailureCoveringContextTask",
        "TaskContext",
        "TaskID",
        "TaskNode",
        "TaskProjection",
        "TaskVar",
        "Workflow",
        "WorkflowException",
        "WorkflowExecutionContext",
        "WorkflowExecutionResult",
        "define_context_task",
        "define_task",
        "define_variable",
        "define_workflow",
    ]
