"""Execution-owned monotonic timing for action and context callback bodies.

Defines ``measure_callback``, ``format_callback_times``.
"""

import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Literal

# Nanoseconds per millisecond follow the SI unit conversion. Integer measurements
# retain monotonic clock precision until the three-decimal log display is rendered.
NANOSECONDS_PER_MILLISECOND = 1_000_000


@contextmanager
def measure_callback(
    times: dict[str, int], phase: Literal["action", "enter", "exit"]
) -> Generator[None]:
    """Measure invocation and awaiting, including failed or cancelled callback bodies.

    :param times: Mutable measurements owned by this execution and task branch.
    :param phase: Callback body being measured, without resource holding time.
    :returns: Scope recording elapsed nanoseconds when its body exits.
    :raises BaseException: Preserve any exception or control signal from the body.
    """
    started = time.perf_counter_ns()
    try:
        yield
    finally:
        times[phase] = time.perf_counter_ns() - started


def format_callback_times(times: Mapping[str, int] | None) -> str:
    """Render only callback phases that ran, in their measured insertion order.

    :param times: Measured nanoseconds by phase, or None before any callback ran.
    :returns: Space-prefixed millisecond fields with three decimal places.
    """
    items = () if times is None else times.items()
    return "".join(
        f" {phase}_ms={duration / NANOSECONDS_PER_MILLISECOND:.3f}" for phase, duration in items
    )
