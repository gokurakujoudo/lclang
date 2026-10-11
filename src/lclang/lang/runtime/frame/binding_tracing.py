# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Frame lookup sources and cache publication diagnostics.

Defines ``describe_binding_execution``, ``trace_binding_value``, ``trace_binding_failure``,
``trace_cached_failure_publication``, ``trace_missing_binding``.
"""

from typing import TYPE_CHECKING

from lclang.error.verbose_diagnostic import internal_render_value, internal_verbose_enabled
from lclang.error.verbose_failure import trace_verbose_failure
from lclang.error.verbose_records import emit_verbose_record
from lclang.lang.runtime.frame.binding_lookup import is_name_masked

if TYPE_CHECKING:
    from lclang.lang.runtime.frame.frame import Frame

# Unitless existing source categories are translated only for human presentation.
SOURCE_LABELS = {
    "cached": "cache",
    "lcl-evaluated": "a new LCL evaluation",
    "shared-lcl-evaluation": "a shared LCL evaluation",
    "native-provided": "native input",
    "external-provided": "external input",
    "fallback": "the fallback",
}


def describe_binding_execution(owner: Frame | None, name: str, kind: str | None) -> str:
    """Describe the selection's current state without evaluating or changing it.

    :param owner: Already-selected owner, or None for a missing lookup.
    :param name: Actual selected binding name.
    :param kind: Existing lookup classification.
    :returns: Short execution-source description.
    """
    if owner is None:
        return "missing binding"
    if kind != "host" and name in owner._results:
        return "cached value"
    if kind != "host" and name in owner._failures:
        return "cached failure"
    if kind != "host" and name in owner.module.definitions:
        return "shared evaluation" if name in owner._inflight else "new evaluation"
    return "native input" if owner.native_values else "external input"


def trace_binding_value(frame: Frame, name: str, source: str, value: object) -> None:
    """Log an already-resolved Frame value with its observed source.

    :param frame: Selected binding owner or fallback requester.
    :param name: Actual binding name.
    :param source: Existing source category.
    :param value: Already-resolved result, never an additional evaluation.
    """
    if internal_verbose_enabled():
        rendered = internal_render_value(value, masked=is_name_masked(frame, name))
        emit_verbose_record(
            "lookup",
            f'Read {name} from {SOURCE_LABELS[source]} in Frame "{frame.frame_id}": {rendered}',
        )


def trace_binding_failure(
    error: BaseException,
    name: str,
    *,
    frame: Frame,
    cached: bool = False,
    phase: str = "resolving a binding",
) -> None:
    """Trace a selected binding failure without expanding its snapshots.

    :param error: Failure produced or returned by the existing lookup.
    :param name: Actual requested binding name.
    :param frame: Selected owner providing masking metadata.
    :param cached: Whether an existing failure cache supplied this observation.
    :param phase: Actual input or evaluation boundary where lookup failed.
    """
    if internal_verbose_enabled():
        trace_verbose_failure(
            error,
            name,
            phase=phase,
            stage="lookup",
            cached=cached,
            masked=is_name_masked(frame, name),
        )


def trace_cached_failure_publication(name: str, error: Exception) -> None:
    """Describe publication only after the existing cache commit succeeds.

    :param name: Actual definition name committed to the failure cache.
    :param error: Committed failure whose identifier was established at detection.
    """
    from lclang.error.exception_base import LclError

    if internal_verbose_enabled() and isinstance(error, LclError):
        identity = error.verbose_failure_id
        if identity is not None:
            emit_verbose_record(
                "evaluate",
                f"Stored the failed evaluation of {name} in cache (failure {identity})",
                failure_id=identity,
            )


def trace_missing_binding(frame: Frame, name: str) -> None:
    """Describe an actual missing selection without rendering an exception.

    :param frame: Requesting Frame.
    :param name: Missing binding name.
    """
    emit_verbose_record("lookup", f'No binding for {name} was found from Frame "{frame.frame_id}"')
