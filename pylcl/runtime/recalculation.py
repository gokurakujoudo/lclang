"""Single-flight coordination for explicit Frame recalculation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


async def _refresh_definition(
    name: str,
    inflight: dict[str, asyncio.Task[object]],
    refreshes: dict[str, asyncio.Task[object]],
    evaluate: Callable[[str], Awaitable[object]],
    ensure_open: Callable[[], None],
) -> object:
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
            refresh = asyncio.create_task(_run_refresh(name, refreshes, evaluate))
            inflight[name] = refresh
            refreshes[name] = refresh
    return await asyncio.shield(refresh)


async def _run_refresh(
    name: str,
    refreshes: dict[str, asyncio.Task[object]],
    evaluate: Callable[[str], Awaitable[object]],
) -> object:
    try:
        return await evaluate(name)
    finally:
        refreshes.pop(name, None)
