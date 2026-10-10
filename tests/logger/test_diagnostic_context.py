"""Logger setup failures retain structured evaluation causes without string nesting."""

import pytest

from lclang.error import LclErrorGroup, LclEvaluationError, LclValidationError, render_failure
from lclang.lang import define_frame, define_module
from lclang.lang.runtime.frame.scoped_proxy import FrameProxy
from lclang.logger import resolve_logger_config


@pytest.mark.asyncio
async def test_logger_field_group_keeps_protocol_members_and_field_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A grouped field lookup failure remains inspectable and identifies its logger setting."""
    original = ExceptionGroup("field", [OSError("first"), ValueError("second")])

    async def broken(proxy: FrameProxy, name: str) -> object:
        raise original

    monkeypatch.setattr(FrameProxy, "get", broken)
    async with define_frame(define_module("logger", {"logger.console.level": "20"})) as frame:
        with pytest.raises(LclErrorGroup) as caught:
            await resolve_logger_config(frame)
    assert caught.value.code == "LCL613291" and caught.value.__cause__ is original
    assert [item.__cause__ for item in caught.value.exceptions] == list(original.exceptions)
    assert "logger setting logger.console" in caught.value.__notes__


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
async def test_logger_adapter_preserves_known_codes_and_classifies_native_failures(
    existing: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Field context is added without overwriting a callback's existing specific code."""
    error = LclEvaluationError("business", code="APP") if existing else OSError("backend")

    async def broken(proxy: FrameProxy, name: str) -> object:
        raise error

    monkeypatch.setattr(FrameProxy, "get", broken)
    async with define_frame(define_module("logger", {"logger.console.level": "20"})) as frame:
        with pytest.raises(LclValidationError) as caught:
            await resolve_logger_config(frame)
    assert caught.value.code == ("APP" if existing else "LCL613291")
    assert caught.value.__cause__ is error and "logger.console" in caught.value.message


@pytest.mark.asyncio
async def test_logger_leaf_failure_keeps_original_diagnostic_as_cause() -> None:
    """Field adapters retain complete evaluation evidence for shared CLI presentation."""
    async with define_frame(define_module("logger", {"logger.console.level": "1 / 0"})) as frame:
        with pytest.raises(LclValidationError) as failure:
            await resolve_logger_config(frame)
        assert "logger.console.level" in str(failure.value)
        assert failure.value.code == "LCL131421"
        cause = failure.value.__cause__
        assert isinstance(cause, LclEvaluationError)
        assert isinstance(cause.__cause__, ZeroDivisionError)
        assert cause.evaluation_context[-1].name == "logger.console.level"
        diagnostic = render_failure(failure.value, action="configuring logging")
        assert diagnostic.startswith("Error in configuring logging [LCL131421]:")
        assert "  Error in evaluating logger.console.level [LCL131421]:" in diagnostic
        assert diagnostic.count("division by zero") == 1
