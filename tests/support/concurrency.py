"""Event-controlled concurrency probes shared by hardening stress tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass(slots=True)
class CountingGate:
    """Count async calls and block selected owners behind an event.

    :param value: Result returned after release.
    :param block_after: Calls at or below this count return immediately.
    :param calls: Number of entered calls.
    :param started: Set when a blocked call reaches the gate.
    :param release: Allows blocked calls to finish.
    """

    value: object
    block_after: int = 0
    calls: int = 0
    started: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def run(self) -> object:
        """Enter the gate and return its current value.

        :returns: Current configured value after any required wait.
        """
        self.calls += 1
        if self.calls > self.block_after:
            self.started.set()
            await self.release.wait()
        return self.value


@dataclass(slots=True)
class AsyncCloseProbe:
    """Record and control asynchronous resource cleanup.

    :param close_calls: Number of close operations entered.
    :param close_started: Set when cleanup begins.
    :param release: Allows cleanup to finish.
    """

    close_calls: int = 0
    close_started: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def aclose(self) -> None:
        """Record one close and wait for explicit release."""
        self.close_calls += 1
        self.close_started.set()
        await self.release.wait()
