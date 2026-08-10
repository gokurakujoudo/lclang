"""Reachability, task, iterator, warning, and allocation leak checks."""

from __future__ import annotations

import asyncio
import gc
import tracemalloc
import warnings
from weakref import ReferenceType

from lclang.runtime import Frame
from lclang.workflow import ExecutionStatusManager
from tests.support.leaks import build_collectible_runtime, run_lifecycle_batch


def collect_until_stable() -> None:
    """Run cyclic collection until no additional objects are reclaimed."""
    while gc.collect():
        pass


def test_closed_frame_closure_iterator_and_tasks_are_collectible() -> None:
    """Owned runtime objects disappear after deterministic close and loop exit."""
    references = asyncio.run(build_collectible_runtime())
    collect_until_stable()
    assert all(reference() is None for reference in references)


def test_repeated_lifecycles_leave_no_types_warnings_or_material_growth() -> None:
    """Warm repeated batches return inventories and traced memory near baseline."""
    collect_until_stable()
    frame_before = sum(isinstance(value, Frame) for value in gc.get_objects())
    workflow_before = sum(isinstance(value, ExecutionStatusManager) for value in gc.get_objects())
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        asyncio.run(run_lifecycle_batch(10))
        collect_until_stable()
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        asyncio.run(run_lifecycle_batch(200))
        collect_until_stable()
        after = tracemalloc.take_snapshot()
        tracemalloc.stop()
    frame_after = sum(isinstance(value, Frame) for value in gc.get_objects())
    workflow_after = sum(isinstance(value, ExecutionStatusManager) for value in gc.get_objects())
    growth = sum(
        max(stat.size_diff, 0)
        for stat in after.compare_to(before, "filename")
        if "lclang" in stat.traceback[0].filename.replace("\\", "/")
    )
    assert (frame_after, workflow_after) == (frame_before, workflow_before)
    assert not [
        warning
        for warning in caught
        if issubclass(warning.category, (ResourceWarning, RuntimeWarning))
    ]
    assert growth < 1_000_000


def test_leak_support_returns_only_weak_references() -> None:
    """Leak probes cannot accidentally retain the objects under inspection."""
    references = asyncio.run(build_collectible_runtime())
    assert all(isinstance(reference, ReferenceType) for reference in references)
