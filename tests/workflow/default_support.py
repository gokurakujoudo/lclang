"""Shared deterministic variable-default workflow fixtures."""

import logging
from dataclasses import dataclass
from datetime import date

import lclang
import lclang.workflow as wf


@dataclass
class Value:
    """One input with a final constructor fallback."""

    value: object = "field-default"


async def echo(
    context: wf.TaskContext, args: Value, status_mgr: wf.ExecutionStatusManager,
) -> Value:
    """Return the resolved input."""
    return args


def execution_context(frame: lclang.Frame) -> wf.WorkflowExecutionContext:
    """Supply deterministic metadata."""
    return wf.WorkflowExecutionContext(
        False, date(2026, 9, 22), False, logging.getLogger("defaults"), frame,
    )


def workflow_for(variable: wf.TaskVar[object]) -> wf.Workflow:
    """Create one minimal input consumer."""
    return wf.define_workflow("Default", wf.define_task(
        "root", "Root", task_action=echo, args_mapping=Value(variable.quote),
    ))


