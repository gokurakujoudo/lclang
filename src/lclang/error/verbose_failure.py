"""First-scene verbose failure summaries and stable diagnostic identities.

Defines ``identify_verbose_failure``, ``trace_verbose_failure``.
"""

from typing import cast

from lclang.error.exception_base import LclError
from lclang.error.failure_summary import describe_failure_reason
from lclang.error.mask_scope import ACTIVE_MASKED_VALUE
from lclang.error.native_wrap import is_ordinary_failure
from lclang.error.verbose_context import (
    ACTIVE_VERBOSE_CONTEXT,
    allocate_verbose_id,
    is_verbose_enabled,
)
from lclang.error.verbose_records import describe_verbose_context, emit_verbose_record


def identify_verbose_failure(error: LclError) -> str:
    """Retain a failure identity through propagation and group membership.

    :param error: Structured ordinary failure already captured by execution.
    :returns: Existing or newly allocated process-local identifier.
    """
    if error.verbose_failure_id is None:
        error.verbose_failure_id = allocate_verbose_id("F")
    if isinstance(error, ExceptionGroup):
        group = cast(ExceptionGroup[Exception], error)
        for member in group.exceptions:
            if isinstance(member, LclError):
                identify_verbose_failure(member)
    return error.verbose_failure_id


def trace_verbose_failure(
    error: BaseException,
    subject: str,
    *,
    phase: str,
    stage: str = "evaluate",
    cached: bool = False,
    masked: bool = False,
) -> str | None:
    """Summarize the first observed failure and reference subsequent observations.

    :param error: Original failure whose cause and snapshots must remain unchanged.
    :param subject: Actual definition, lookup, or operation being observed.
    :param phase: Operation phase known at the detecting boundary.
    :param stage: Stable machine-readable trace stage.
    :param cached: Whether this observation came from a pre-existing failure cache.
    :param masked: Whether the selected binding requires reason redaction.
    :returns: Failure identifier, or None for inactive tracing or native controls.
    """
    if (
        not is_verbose_enabled()
        or not is_ordinary_failure(error)
        or not isinstance(error, LclError)
    ):
        return None
    masked = (
        masked
        or ACTIVE_MASKED_VALUE.get()
        or error.masked
        or any(frame.masked for frame in error.evaluation_context)
    )
    first = error.verbose_failure_id is None
    if first and isinstance(error, ExceptionGroup):
        group = cast(ExceptionGroup[Exception], error)
        for index, member in enumerate(group.exceptions, 1):
            if isinstance(member, LclError) and member.verbose_failure_id is None:
                trace_verbose_failure(
                    member,
                    f"{subject} / member {index}",
                    phase=phase,
                    stage=stage,
                    cached=cached,
                    masked=masked,
                )
    identity = identify_verbose_failure(error)
    if first:
        reason = describe_failure_reason(error, masked=masked)
        if cached:
            heading = f"Observed a cached failure of {subject}"
        elif stage == "parse":
            heading = f"Failed to parse {subject}"
        elif stage == "lookup":
            heading = f"Failed to read {subject}"
        elif stage == "command":
            heading = f"Failed during {subject}"
        else:
            heading = f"Failed while evaluating {subject}"
        details = [("Type", type(error).__name__)]
        if error.span is not None and str(error.span.origin.name) != "<unknown>":
            from lclang.error.source_excerpt import render_source_location

            details.append(("Source", render_source_location(error.span)))
        details.extend(describe_verbose_context())
        details.append(("Phase", phase))
        if cached:
            details.append(("History", "original evaluation was not traced; no new evaluation"))
        if isinstance(error, ExceptionGroup):
            group = cast(ExceptionGroup[Exception], error)
            members = tuple(
                member.verbose_failure_id
                for member in group.exceptions
                if isinstance(member, LclError)
            )
            details.append(("Members", ", ".join(value for value in members if value is not None)))
        emit_verbose_record(
            stage,
            f"{heading} [{error.code}: {reason}] (failure {identity})",
            details=tuple(details),
            failure_id=identity,
        )
    else:
        if cached:
            heading = f"Returned the cached failure of {subject}; no new evaluation"
        elif ACTIVE_VERBOSE_CONTEXT.get().execution == "shared evaluation":
            heading = f"Returned the failed shared evaluation of {subject}"
        else:
            frames = error.evaluation_context
            dependency = frames[-1].name if frames else "an evaluation"
            for index in range(len(frames) - 2, -1, -1):
                if frames[index].name == subject:
                    dependency = frames[index + 1].name
                    break
            heading = (
                f"Returned the failed evaluation of {subject}"
                if dependency == subject
                else f"Could not complete {subject} because {dependency} failed"
            )
        emit_verbose_record(stage, f"{heading} (failure {identity})", failure_id=identity)
    return identity
