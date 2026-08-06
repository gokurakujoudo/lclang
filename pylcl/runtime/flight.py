"""Task-local dependency paths for Frame single-flight ownership."""

from __future__ import annotations

from contextvars import ContextVar, Token

from pylcl.errors import LclCircularDependencyError
from pylcl.source import SourceSpan

type FlightKey = tuple[int, str]
type FlightPath = tuple[FlightKey, ...]

_ACTIVE_FLIGHTS: ContextVar[FlightPath] = ContextVar(
    "pylcl_active_frame_flights",
    default=(),
)


def _check_cycle(owner: object, name: str, span: SourceSpan | None) -> None:
    path = _ACTIVE_FLIGHTS.get()
    key = (id(owner), name)
    if key not in path:
        return
    start = path.index(key)
    names = [entry_name for _, entry_name in path[start:]]
    names.append(name)
    message = f"circular dependency: {' -> '.join(names)}"
    raise LclCircularDependencyError(message, span=span)


def _enter_flight(owner: object, name: str) -> Token[FlightPath]:
    path = _ACTIVE_FLIGHTS.get()
    return _ACTIVE_FLIGHTS.set((*path, (id(owner), name)))


def _leave_flight(token: Token[FlightPath]) -> None:
    _ACTIVE_FLIGHTS.reset(token)
