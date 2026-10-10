"""Logger setup failures retain structured evaluation causes without string nesting."""

import pytest

from lclang import define_frame, define_module
from lclang.error_rendering import render_failure
from lclang.errors import LclEvaluationError
from lclang.logger import resolve_logger_config


@pytest.mark.asyncio
async def test_logger_leaf_failure_keeps_original_diagnostic_as_cause() -> None:
    """Field adapters retain complete evaluation evidence for shared CLI presentation."""
    async with define_frame(define_module("logger", {"logger.console.level": "1 / 0"})) as frame:
        with pytest.raises(ValueError) as failure:
            await resolve_logger_config(frame)
        assert "logger.console.level" in str(failure.value)
        assert "Error in" not in str(failure.value)
        cause = failure.value.__cause__
        assert isinstance(cause, LclEvaluationError)
        assert isinstance(cause.__cause__, ZeroDivisionError)
        assert cause.evaluation_context[-1].name == "logger.console.level"
        diagnostic = render_failure(failure.value, action="configuring logging")
        assert diagnostic.startswith("Error in configuring logging:")
        assert "  Error in evaluating logger.console.level [LCL3001]:" in diagnostic
        assert diagnostic.count("division by zero") == 1
