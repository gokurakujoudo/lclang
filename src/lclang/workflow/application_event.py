"""Explicit application event selection, masking, and logger forwarding.

Defines ``emit_event``.
"""

from collections.abc import Iterable, Mapping
from dataclasses import fields as record_fields
from dataclasses import is_dataclass
from typing import TYPE_CHECKING

from lclang.error import LclWorkflowError, WorkflowErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.utils.value_representation import align_repr_fields, make_multi_log_lines, safe_repr

if TYPE_CHECKING:
    from lclang.workflow.execution_context import TaskContext


@guard_failure(LclWorkflowError, WorkflowErrorCode.E34_WORKFLOW_EVENT_NATIVE_FAILURE)
def emit_event(
    context: TaskContext,
    event: str,
    level: int,
    record: object | None,
    fields: Iterable[str],
    masked_fields: Iterable[str],
    values: Mapping[str, object],
) -> None:
    """Render explicitly selected values after level admission and mask checks.

    :param context: Task metadata and execution logger.
    :param event: Application event name.
    :param level: Standard-library numeric log severity.
    :param record: Optional dataclass instance containing selected fields.
    :param fields: Ordered direct dataclass field names.
    :param masked_fields: Selected or keyword names to redact before reading.
    :param values: Additional named application values.
    :raises LclValidationError: If an enabled event supplies a non-dataclass record.
    :raises LclValidationError: If fields are missing, duplicated, or conflict with keyword values.
    :raises Exception: If an unmasked selected getter or logger raises.
    """
    if not context.logger.isEnabledFor(level):
        return
    selected = tuple(fields)
    masked = frozenset(masked_fields)
    if record is not None and (not is_dataclass(record) or isinstance(record, type)):
        raise LclValidationError(
            "event record must be a dataclass instance",
            code=WorkflowErrorCode.E34_EVENT_RECORD_MUST_BE_A_DATACLASS_INSTANCE,
        )
    declared: set[str] = set() if record is None else {item.name for item in record_fields(record)}
    if (
        set(selected) - declared
        or len(set(selected)) != len(selected)
        or set(selected) & values.keys()
    ):
        raise LclValidationError(
            "event fields must be declared, unique, and separate from keyword values",
            code=WorkflowErrorCode.E34_EVENT_FIELDS_MUST_BE_DECLARED_UNIQUE_AND_SEPARATE_FROM_KEYWORD_VA,
        )
    rendered: list[tuple[str, str]] = []
    for name in selected:
        value = None if name in masked else getattr(record, name)
        rendered.append((name, safe_repr(value, masked=name in masked)))
    rendered.extend(
        (name, safe_repr(value, masked=name in masked)) for name, value in values.items()
    )
    branch = ".".join(context.task_id_stack)
    dryrun = " (dryrun)" if context.is_dryrun else ""
    message = f"event {safe_repr(event)}: [{branch}]{dryrun}"
    message = make_multi_log_lines(message, align_repr_fields(rendered))
    context.logger.log(
        level,
        message,
        stacklevel=5,
        extra={
            "lclang_event": event,
            "lclang_task_branch": branch,
            "lclang_dryrun": context.is_dryrun,
        },
    )
