"""Task-local dependency paths for Frame evaluation flights."""

from __future__ import annotations

from contextvars import ContextVar, Token

from lclang.errors import LclCircularDependencyError
from lclang.source import SourceSpan

type FlightKey = tuple[int, str]
type FlightPath = tuple[FlightKey, ...]

_ACTIVE_FLIGHTS: ContextVar[FlightPath] = ContextVar(
    "lclang_active_frame_flights",
    default=(),
)


def internal_check_cycle(owner: object, name: str, span: SourceSpan | None) -> None:
    """Reject re-entry of one owner/name pair in the active task path.

    :param owner: Frame owning the requested definition.
    :param name: Definition requested by evaluation.
    :param span: Optional source span of the requesting name.
    :raises LclCircularDependencyError: If the pair already appears in the path.
    """
    path = _ACTIVE_FLIGHTS.get()
    key = (id(owner), name)
    if key not in path:
        return
    start = path.index(key)
    names = [entry_name for _, entry_name in path[start:]]
    names.append(name)
    message = f"circular dependency: {' -> '.join(names)}"
    raise LclCircularDependencyError(message, span=span)


def internal_enter_flight(owner: object, name: str) -> Token[FlightPath]:
    """Append one owner/name pair to task-local flight state.

    :param owner: Frame owning the definition.
    :param name: Definition beginning evaluation.
    :returns: Context token used to restore the prior path.
    """
    path = _ACTIVE_FLIGHTS.get()
    return _ACTIVE_FLIGHTS.set((*path, (id(owner), name)))


def internal_leave_flight(token: Token[FlightPath]) -> None:
    """Restore task-local flight state after evaluation.

    :param token: Token returned by :func:`_enter_flight`.
    """
    _ACTIVE_FLIGHTS.reset(token)
