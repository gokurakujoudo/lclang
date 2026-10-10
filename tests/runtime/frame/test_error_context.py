"""Source-aware failure snapshots without diagnostic reevaluation."""

import pytest

from lclang import define_frame, define_module
from lclang.error import LclEvaluationError


@pytest.mark.asyncio
async def test_failure_keeps_used_values_source_and_cached_identity() -> None:
    """A failure describes only values actually read and retains its first snapshot."""
    module = define_module("metrics", {"ratio": "total / count", "result": "ratio * 100"})
    async with define_frame(module, preset={"total": 5, "count": 0, "unused": "private"}) as frame:
        with pytest.raises(LclEvaluationError) as first:
            await frame.get("result")
        diagnostic = str(first.value)
        assert diagnostic.startswith("Error in evaluating result [LCL131421]:\n")
        assert "total / count" in diagnostic
        assert "total = (int) 5" in diagnostic
        assert "count = (int) 0" in diagnostic
        assert "unused" not in diagnostic
        assert isinstance(first.value.__cause__, ZeroDivisionError)
        frame.mixin({"count": 2})
        with pytest.raises(LclEvaluationError) as second:
            await frame.get("result")
        assert second.value is first.value
        assert str(second.value) == diagnostic
