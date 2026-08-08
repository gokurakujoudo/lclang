"""Reusable owned-resource doubles for Frame lifecycle tests."""

import asyncio


class SyncResource:
    """Record synchronous close calls with an optional failure."""

    def __init__(
        self,
        name: str,
        events: list[str],
        error: Exception | None = None,
    ) -> None:
        """Store resource identity, event sink, and optional failure."""
        self.name = name
        self.events = events
        self.error = error
        self.calls = 0

    def close(self) -> None:
        """Record one close attempt and optionally fail."""
        self.calls += 1
        self.events.append(self.name)
        if self.error is not None:
            raise self.error


class AsyncResource:
    """Record asynchronous close calls."""

    def __init__(self, name: str, events: list[str]) -> None:
        """Store resource identity and event sink."""
        self.name = name
        self.events = events
        self.calls = 0

    async def aclose(self) -> None:
        """Record one asynchronous close completion."""
        await asyncio.sleep(0)
        self.calls += 1
        self.events.append(self.name)


class BlockingResource:
    """Hold asynchronous cleanup until a test releases it."""

    def __init__(self) -> None:
        """Create cleanup coordination events."""
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def aclose(self) -> None:
        """Signal cleanup, wait for release, and record completion."""
        self.started.set()
        await self.release.wait()
        self.calls += 1


class CancellingResource:
    """Raise direct cancellation during owned cleanup."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event sink."""
        self.events = events

    async def aclose(self) -> None:
        """Record the attempt and raise direct cancellation."""
        self.events.append("cancel")
        raise asyncio.CancelledError
