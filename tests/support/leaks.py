"""Runtime construction helpers that retain only weak leak probes."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import cast
from weakref import ReferenceType, ref

import lclang
from lclang.errors import LclEvaluationError
from lclang.workflow import ExecutionStatusManager
from tests.support.concurrency import CountingGate


async def build_collectible_runtime() -> tuple[ReferenceType[object], ...]:
    """Build, close, and weakly reference a composite runtime lifecycle.

    :returns: Weak references to the Frame, closure, iterator, and cancelled task.
    """
    gate = CountingGate(99)
    frame = lclang.Frame(
        lclang.define_module(
            "leak-probe",
            {
                "closure": "(value) -> value + 1",
                "iterator": "(item for item in values)",
                "slow": "work()",
            },
        ),
        values={"values": range(3), "work": gate.run},
    )
    closure = await frame.get("closure")
    iterator = await frame.get("iterator")
    task = asyncio.create_task(frame.get("slow"))
    await gate.started.wait()
    references = tuple(
        cast(ReferenceType[object], ref(value)) for value in (frame, closure, iterator, task)
    )
    await frame.close()
    await asyncio.gather(task, return_exceptions=True)
    return references


async def run_lifecycle_batch(count: int) -> None:
    """Run repeated Frame, closure, failure, iterator, and workflow lifecycles.

    :param count: Positive number of independent lifecycles.
    :returns: ``None`` after every owned object is finalized and dropped.
    :raises ValueError: If *count* is not positive.
    """
    if count <= 0:
        raise ValueError("lifecycle batch count must be positive")
    for index in range(count):
        frame = lclang.Frame(
            lclang.define_module(
                f"batch-{index}",
                {
                    "closure": "(value) -> value + 1",
                    "iterator": "(item for item in values)",
                    "failure": "1 / zero",
                },
            ),
            values={"values": range(3), "zero": 0},
        )
        await frame.get("closure")
        iterator = await frame.get("iterator")
        del iterator
        with suppress(LclEvaluationError):
            await frame.get("failure")
        await frame.close()
        workflow = ExecutionStatusManager(f"batch-{index}")
        with workflow.add_step("done", "complete"):
            pass
        workflow.finalize()
