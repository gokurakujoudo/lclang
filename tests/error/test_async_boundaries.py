"""Async native failures are classified by their owning operation boundary."""

import pytest

from lclang.common.awaitable_resolution import resolve_operation_value
from lclang.error import LclEvaluationError, LclUtilityError, LclValidationError
from lclang.lang import define_frame, define_module
from lclang.utils import invoke


@pytest.mark.asyncio
async def test_awaited_callback_uses_the_call_failure_code() -> None:
    """Awaiting a business callback does not replace its operation classification."""
    native = OSError("callback")

    async def fail() -> None:
        raise native

    async with define_frame(
        define_module("callback", {"result": "fail()"}), preset={"fail": fail}
    ) as frame:
        with pytest.raises(LclEvaluationError) as caught:
            await frame.get("result")
        assert caught.value.code == "LCL132811"
        assert caught.value.__cause__ is native


@pytest.mark.asyncio
async def test_awaited_resource_cleanup_uses_the_cleanup_failure_code() -> None:
    """A failing async close retains its resource owner and final closed state."""
    native = OSError("close")

    class Resource:
        async def aclose(self) -> None:
            raise native

    resource = Resource()
    frame = define_frame(
        define_module("resource", {"value": "make()"}), preset={"make": lambda: resource}
    )
    assert await frame.get("value") is resource
    with pytest.raises(LclEvaluationError) as caught:
        await frame.close()
    assert caught.value.code == "LCL236811"
    assert caught.value.__cause__ is native and frame.closed


@pytest.mark.asyncio
async def test_awaited_utility_callback_keeps_its_utility_family() -> None:
    """Python utility invocation retains utility classification for async callbacks."""
    native = OSError("invoke")

    async def fail() -> None:
        raise native

    with pytest.raises(LclUtilityError) as caught:
        await invoke(fail)
    assert caught.value.code == "LCL771811" and caught.value.__cause__ is native


@pytest.mark.asyncio
async def test_operation_awaiting_preserves_existing_codes_and_native_control() -> None:
    """Operation metadata never replaces a known LCL error or iteration signal."""
    failures: tuple[Exception, ...] = (
        LclValidationError("known", code="APP/KNOWN"),
        StopAsyncIteration(),
    )
    for failure in failures:

        async def fail(error: Exception = failure) -> None:
            raise error

        with pytest.raises(Exception) as caught:
            await resolve_operation_value(fail(), LclEvaluationError, "LCL133890")
        assert caught.value is failure
    assert await resolve_operation_value(42, LclEvaluationError, "LCL133890") == 42
