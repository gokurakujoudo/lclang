"""Root-scoped summaries of observed failure propagation and cache commits.

Defines ``VerboseFailureBatch``, ``scope_verbose_failure_batch``,
``collect_verbose_failure_event``, ``emit_verbose_failure_batch``.
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from lclang.error.exception_base import LclError
from lclang.error.native_wrap import is_ordinary_failure
from lclang.error.using_diagnostics import describe_using_subject
from lclang.error.verbose_context import (
    ACTIVE_VERBOSE_LOGGER,
    VerboseLogger,
    is_verbose_enabled,
)
from lclang.error.verbose_guard import ignore_verbose_failure
from lclang.error.verbose_records import emit_verbose_record


@dataclass(slots=True)
class VerboseFailureBatch:
    """Retain only detached text while a root request and its owner Tasks run.

    :param name: Actual root binding or expression label.
    :param logger: Borrowed destination distinguishing nested logger scopes.
    :param events: Failure identifiers mapped to ordered category/text pairs.
    :param active: Whether producers may still defer events into this request.
    """

    name: str
    logger: VerboseLogger
    events: dict[str, list[tuple[str, str]]] = field(
        default_factory=lambda: dict[str, list[tuple[str, str]]]()
    )
    active: bool = True


# Unitless task-local batches are inherited by owned evaluation Tasks. Closing a
# root stops deferral so a surviving shielded owner cannot lose later events.
ACTIVE_VERBOSE_FAILURE_BATCH: ContextVar[VerboseFailureBatch | None] = ContextVar(
    "lclang_verbose_failure_batch", default=None
)


@contextmanager
def scope_verbose_failure_batch(name: str) -> Generator[None]:
    """Summarize actual failure events when the enclosing root finishes.

    :param name: Actual root request, without another binding lookup.
    :returns: Scope restoring previous state on normal, failed or cancelled exit.
    """
    logger = ACTIVE_VERBOSE_LOGGER.get()
    if logger is None or not is_verbose_enabled():
        yield
        return
    previous = ACTIVE_VERBOSE_FAILURE_BATCH.get()
    if previous is not None and previous.active and previous.logger is logger:
        yield
        return
    batch = VerboseFailureBatch(name, logger)
    token = ACTIVE_VERBOSE_FAILURE_BATCH.set(batch)
    failed_id = None
    try:
        yield
    except BaseException as error:
        with ignore_verbose_failure():
            if is_ordinary_failure(error) and isinstance(error, LclError):
                failed_id = error.verbose_failure_id
        raise
    finally:
        batch.active = False
        try:
            with ignore_verbose_failure():
                if ACTIVE_VERBOSE_LOGGER.get() is logger and is_verbose_enabled():
                    emit_verbose_failure_batch(batch, failed_id)
        finally:
            batch.events.clear()
            ACTIVE_VERBOSE_FAILURE_BATCH.reset(token)


def collect_verbose_failure_event(identity: str, category: str, text: str) -> bool:
    """Defer an already-observed event into the current destination's root.

    :param identity: Existing failure identifier established at first observation.
    :param category: Propagation, committed cache or cache-owner metadata category.
    :param text: Detached event text, never a Frame, exception or host value.
    :returns: Whether the caller should omit its individual event record.
    """
    batch = ACTIVE_VERBOSE_FAILURE_BATCH.get()
    if (
        batch is None
        or not batch.active
        or batch.logger is not ACTIVE_VERBOSE_LOGGER.get()
        or not is_verbose_enabled()
    ):
        return False
    batch.events.setdefault(identity, []).append((category, text))
    return True


def emit_verbose_failure_batch(batch: VerboseFailureBatch, failed_id: str | None) -> None:
    """Emit one compact record per observed failure after actual cache commits.

    :param batch: Completed root containing text-only event snapshots.
    :param failed_id: Root's final ordinary failure identifier, or None after recovery/control.
    """
    for identity, events in batch.events.items():
        cached = tuple(text for category, text in events if category == "Cached failures")
        heading = (
            f"Could not evaluate {describe_using_subject(batch.name)}"
            if identity == failed_id
            else f"Failure observed while evaluating {describe_using_subject(batch.name)}"
        )
        details = (
            ()
            if not cached
            else (("Cached failures", ", ".join(describe_using_subject(name) for name in cached)),)
        )
        metadata = tuple(
            (category, "; ".join(text for kind, text in events if kind == category))
            for category in ("Propagation", "Cache owners")
            if any(kind == category for kind, _ in events)
        )
        emit_verbose_record(
            "evaluate",
            f"{heading} (failure {identity})",
            details=details,
            failure_id=identity,
            context_details=details + metadata,
        )
