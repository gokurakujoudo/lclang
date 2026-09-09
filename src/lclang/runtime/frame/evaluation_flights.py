"""Task-local dependency paths for Frame evaluation flights."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from contextvars import ContextVar, Token

from lclang.errors import LclCircularDependencyError
from lclang.source import SourceSpan

type FlightKey = tuple[int, str]
type FlightPath = tuple[FlightKey, ...]

# Task-local active evaluation paths start empty; entries identify Frame/name pairs to detect
# cycles without mixing concurrent tasks.
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






async def internal_refresh_definition(
    name: str,
    inflight: dict[str, asyncio.Task[object]],
    refreshes: dict[str, asyncio.Task[object]],
    evaluate: Callable[[str], Awaitable[object]],
    ensure_open: Callable[[], None],
) -> object:
    """Join or create one shielded recalculation flight.

    :param name: Definition selected for recalculation.
    :param inflight: Initial/refresh tasks visible to ordinary requests.
    :param refreshes: Active recalculation tasks by definition.
    :param evaluate: Callback performing a fresh definition evaluation.
    :param ensure_open: Lifecycle callback checked before task creation.
    :returns: Recalculated value.
    """
    refresh = refreshes.get(name)
    if refresh is None:
        initial = inflight.get(name)
        if initial is not None:
            try:
                await asyncio.shield(initial)
            except asyncio.CancelledError:
                if not initial.cancelled():
                    raise
            except Exception:
                pass
        refresh = refreshes.get(name)
        if refresh is None:
            ensure_open()
            refresh = asyncio.create_task(internal_run_refresh(name, refreshes, evaluate))
            inflight[name] = refresh
            refreshes[name] = refresh
    return await asyncio.shield(refresh)


async def internal_run_refresh(
    name: str,
    refreshes: dict[str, asyncio.Task[object]],
    evaluate: Callable[[str], Awaitable[object]],
) -> object:
    """Evaluate one refresh and remove its refresh-only registration.

    :param name: Definition selected for recalculation.
    :param refreshes: Active recalculation tasks by definition.
    :param evaluate: Callback performing the fresh evaluation.
    :returns: Recalculated value.
    """
    try:
        return await evaluate(name)
    finally:
        refreshes.pop(name, None)
