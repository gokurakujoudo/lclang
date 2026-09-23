"""Explicit application event selection, masking, and logger forwarding."""

from collections.abc import Iterable, Mapping
from dataclasses import fields as record_fields
from dataclasses import is_dataclass
from typing import TYPE_CHECKING

from lclang.utils.representation import align_repr_fields, make_multi_log_lines, safe_repr

if TYPE_CHECKING:
    from lclang.workflow.context import TaskContext


def emit_event(
    context: TaskContext, event: str, level: int, record: object | None,
    fields: Iterable[str], masked_fields: Iterable[str], values: Mapping[str, object],
) -> None:
    """Render explicitly selected values after level admission and mask checks.

    :param context: Task metadata and execution logger.
    :param event: Application event name.
    :param level: Standard-library numeric log severity.
    :param record: Optional dataclass instance containing selected fields.
    :param fields: Ordered direct dataclass field names.
    :param masked_fields: Selected or keyword names to redact before reading.
    :param values: Additional named application values.
    :raises TypeError: If an enabled event supplies a non-dataclass record.
    :raises ValueError: If fields are missing, duplicated, or conflict with keyword values.
    :raises Exception: If an unmasked selected getter or logger raises.
    """
    if not context.logger.isEnabledFor(level):
        return
    selected = tuple(fields)
    masked = frozenset(masked_fields)
    if record is not None and (not is_dataclass(record) or isinstance(record, type)):
        raise TypeError("event record must be a dataclass instance")
    declared = set() if record is None else {item.name for item in record_fields(record)}
    if (
        set(selected) - declared or len(set(selected)) != len(selected)
        or set(selected) & values.keys()
    ):
        raise ValueError("event fields must be declared, unique, and separate from keyword values")
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
    context.logger.log(level, message, stacklevel=3, extra={
        "lclang_event": event, "lclang_task_branch": branch, "lclang_dryrun": context.is_dryrun,
    })
