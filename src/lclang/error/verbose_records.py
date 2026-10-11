"""Readable DEBUG records with immutable producer-side context.

Defines ``describe_verbose_context``, ``emit_verbose_record``.
"""

import asyncio

from lclang.error.verbose_context import ACTIVE_VERBOSE_CONTEXT, ACTIVE_VERBOSE_LOGGER
from lclang.utils.value_representation import safe_repr


def describe_verbose_context() -> tuple[tuple[str, str], ...]:
    """Detach the context already obtained by execution and lookup.

    :returns: Immutable text field pairs, without Frames or host objects.
    """
    context = ACTIVE_VERBOSE_CONTEXT.get()
    fields: list[tuple[str, str]] = []
    if context.evaluation_id is not None:
        fields.append(("Evaluation", context.evaluation_id))
    if context.request_path:
        fields.append(("Request", " -> ".join(context.request_path)))
    if context.requester is not None:
        frames = f'requested from "{context.requester}"'
        if context.owner is not None:
            frames += f'; defined in "{context.owner}"'
        fields.append(("Frames", frames))
    if context.lookup_path:
        fields.append(("Lookup path", " -> ".join(context.lookup_path)))
    if context.execution is not None:
        fields.append(("Execution", context.execution))
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    if task is not None:
        fields.append(("Task", task.get_name()))
    return tuple((name, safe_repr(value, renderer=str, max_length=None)) for name, value in fields)


def emit_verbose_record(
    stage: str,
    heading: str,
    *,
    details: tuple[tuple[str, str], ...] = (),
    failure_id: str | None = None,
) -> None:
    """Send a readable diagnostic through the borrowed logger.

    :param stage: Stable machine-readable stage for external filters.
    :param heading: Short English description of the actual operation.
    :param details: Already-protected text details shown in fixed order.
    :param failure_id: Original failure identifier when the event refers to an error.
    """
    logger = ACTIVE_VERBOSE_LOGGER.get()
    if logger is None or not logger.isEnabledFor(10):
        return
    context = describe_verbose_context()
    message = "\n".join(
        (
            safe_repr(heading, renderer=str, max_length=None),
            *(
                f"  {name}: {safe_repr(value, renderer=str, max_length=None)}"
                for name, value in details
            ),
        )
    )
    logger.debug(
        "%s",
        message,
        stacklevel=3,
        extra={
            "lclang_verbose": True,
            "lclang_stage": stage,
            "lclang_evaluation_id": ACTIVE_VERBOSE_CONTEXT.get().evaluation_id,
            "lclang_failure_id": failure_id,
            "lclang_context": context,
        },
    )
