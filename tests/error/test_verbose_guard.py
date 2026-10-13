"""Optional diagnostic boundaries discard ordinary errors and retain controls."""

import asyncio

import pytest

from lclang.error import LclError
from lclang.error.verbose_guard import guard_verbose_operation, ignore_verbose_failure


def test_guard_preserves_arguments_results_and_function_metadata() -> None:
    """Healthy diagnostic functions retain their result and invocation signature."""

    @guard_verbose_operation
    def describe(value: int, *, scale: int) -> str:
        """Describe one supplied value."""
        return str(value * scale)

    assert describe(21, scale=2) == "42"
    assert describe.__name__ == "describe"


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("render"),
        RecursionError("cycle"),
        LclError("log"),
        ExceptionGroup("rendering", [ValueError("first"), RuntimeError("second")]),
    ],
)
def test_optional_diagnostics_discard_ordinary_errors(failure: Exception) -> None:
    """Both producer and phase boundaries discard only ordinary diagnostic failure."""

    @guard_verbose_operation
    def fail() -> int:
        """Produce the selected diagnostic failure."""
        raise failure

    assert fail() is None
    with ignore_verbose_failure():
        raise failure
    with pytest.raises(type(failure)) as caught, ignore_verbose_failure(required=True):
        raise failure
    assert caught.value is failure


@pytest.mark.parametrize(
    "signal",
    [
        asyncio.CancelledError(),
        SystemExit(9),
        KeyboardInterrupt(),
        StopIteration(),
        StopAsyncIteration(),
        ExceptionGroup("control", [StopAsyncIteration()]),
    ],
)
def test_diagnostic_phases_retain_native_signals(signal: BaseException) -> None:
    """Cancellation and iterator controls survive optional phase isolation."""
    with pytest.raises(type(signal)) as caught, ignore_verbose_failure():
        raise signal
    assert caught.value is signal
