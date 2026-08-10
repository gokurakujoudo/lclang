"""Single-flight coordination for Frame recalculation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


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
