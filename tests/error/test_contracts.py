"""Structured constructors, protocol behavior, and cause-preserving operation guards."""

import asyncio
from collections.abc import Awaitable, Callable
from copy import copy
from dataclasses import FrozenInstanceError
from datetime import date
from typing import cast

import pytest

from lclang.common.source_location import UNKNOWN_SPAN, SourcePosition, SourceSpan
from lclang.error import (
    CalendarCannotLoadException,
    DateOperationOutOfScopeException,
    LclAttributeError,
    LclError,
    LclErrorGroup,
    LclFrozenAttributeError,
    LclValidationError,
)
from lclang.error.diagnostic_records import ConfigLoadFrame
from lclang.error.failure_aggregation import combine_failures
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_async_failure, guard_failure
from lclang.lang import LclRecord, define_module
from lclang.utils.calendar.business_calendar import BDCalendar
from lclang.utils.calendar.calendar_type import CalendarID


@pytest.mark.parametrize(
    "constructor,code",
    [
        (lambda: LclError(""), "LCL011211"),
        (lambda: LclError("bad", code=""), "LCL011211"),
        (lambda: LclError(cast(str, 1)), "LCL011111"),
        (lambda: LclError("bad", span=cast(SourceSpan, 1)), "LCL011181"),
        (lambda: cast(Callable[..., LclError], LclError)(), "LCL011191"),
        (lambda: LclErrorGroup("group", []), "LCL021111"),
        (lambda: CalendarCannotLoadException(cast(CalendarID, 1)), "LCL711111"),
        (lambda: CalendarCannotLoadException(CalendarID("")), "LCL711211"),
        (
            lambda: DateOperationOutOfScopeException(cast(date, 1), cast(BDCalendar, None)),
            "LCL711171",
        ),
        (
            lambda: DateOperationOutOfScopeException(date(2026, 1, 1), cast(BDCalendar, None)),
            "LCL711173",
        ),
    ],
)
def test_error_construction_fails_safely(constructor: Callable[[], LclError], code: str) -> None:
    """Verify error construction fails safely."""
    with pytest.raises(LclValidationError) as caught:
        constructor()
    assert caught.value.code == code
    assert not isinstance(caught.value, (TypeError, ValueError))
    assert code in str(caught.value)


def test_native_constructor_failure_cannot_recurse() -> None:
    """Verify native constructor failure cannot recurse."""

    class BrokenError(LclError):
        def __init__(self) -> None:
            raise OSError("constructor failed")

    with pytest.raises(LclValidationError) as caught:
        BrokenError()
    assert caught.value.code == "LCL011891"
    assert isinstance(caught.value.__cause__, OSError)


def test_attribute_defaults_and_frozen_protocols_keep_python_behavior() -> None:
    """Verify attribute defaults and frozen protocols keep python behavior."""
    record = LclRecord({"value": 1})
    assert hasattr(record, "value") and not hasattr(record, "absent")
    assert getattr(record, "absent", 42) == 42
    with pytest.raises(LclAttributeError) as absent:
        getattr(record, "absent")  # noqa: B009
    assert isinstance(absent.value, AttributeError)
    position = SourcePosition(1, 1, 0)
    with pytest.raises(LclFrozenAttributeError) as frozen:
        setattr(position, "line", 2)  # noqa: B010
    assert isinstance(frozen.value, FrozenInstanceError)
    assert frozen.value.code == "LCL013611"


@pytest.mark.parametrize("value", [None, True, 1.5, "1"])
def test_source_coordinate_type_is_distinct_from_range(value: object) -> None:
    """Verify source coordinate type is distinct from range."""
    with pytest.raises(LclValidationError) as caught:
        SourcePosition(cast(int, value), 1, 0)
    assert caught.value.code == "LCL811141"
    with pytest.raises(LclValidationError) as line:
        SourcePosition(0, 1, 0)
    with pytest.raises(LclValidationError) as column:
        SourcePosition(1, 0, 0)
    assert line.value.code == column.value.code == "LCL811221"


def test_native_wrappers_and_loading_copies_retain_specific_failures() -> None:
    """Verify native wrappers and loading copies retain specific failures."""
    native = ValueError("business")
    wrapped = wrap_failure(native, LclError, "APP")
    assert wrapped.__cause__ is native
    assert wrap_failure(wrapped, LclError, "OTHER") is wrapped
    wrapped.add_note("operation")
    derived = wrapped.derive_config_context(ConfigLoadFrame(UNKNOWN_SPAN.origin))
    derived.add_note("caller")
    assert derived is not wrapped and derived.code == "APP"
    assert derived.__cause__ is native and wrapped.__notes__ == ["operation"]
    assert copy(wrapped).args == wrapped.args
    assert copy(wrapped).__cause__ is native


def test_groups_preserve_member_identity_and_python_splitting() -> None:
    """Verify groups preserve member identity and python splitting."""
    first = LclValidationError("first", code="ONE")
    native = ValueError("second")
    group = LclErrorGroup("both", [first, native], code="GROUP")
    assert group.exceptions[0] is first
    assert group.exceptions[1].__cause__ is native
    selected, other = group.split(LclValidationError)
    assert isinstance(selected, LclErrorGroup) and isinstance(other, LclErrorGroup)
    assert selected.code == other.code == "GROUP"
    assert selected.exceptions == (first,)
    assert other.exceptions == (group.exceptions[1],)
    assert copy(group).exceptions == group.exceptions
    assert "Failure 1" in str(group) and "Failure 2" in str(group)
    assert group.subgroup(LclValidationError) is not None
    group.__cause__ = native
    group.add_note("operation")
    detached = copy(group)
    detached.add_note("caller")
    assert detached.__cause__ is native and group.__notes__ == ["operation"]


@pytest.mark.parametrize(
    "signal", [KeyboardInterrupt("stop"), SystemExit(2), StopIteration(), StopAsyncIteration()]
)
def test_sync_guard_preserves_native_control_signals(signal: BaseException) -> None:
    """Verify sync guard preserves native control signals."""

    @guard_failure(LclError, "APP")
    def fail() -> None:
        raise signal

    with pytest.raises(type(signal)) as caught:
        fail()
    assert caught.value is signal


@pytest.mark.asyncio
async def test_async_guards_preserve_cancellation_and_classify_signatures() -> None:
    """Verify async guards preserve cancellation and classify signatures."""
    signal = asyncio.CancelledError("stop")

    @guard_async_failure(LclError, "APP")
    async def fail(value: int) -> None:
        raise signal

    with pytest.raises(asyncio.CancelledError) as caught:
        await fail(1)
    assert caught.value is signal
    with pytest.raises(LclValidationError) as signature:
        await cast(Callable[..., Awaitable[None]], fail)()
    assert signature.value.code == "LCL031191"
    with pytest.raises(LclValidationError) as sync_signature:
        cast(Callable[..., object], define_module)()
    assert sync_signature.value.code == "LCL031191"


def test_aggregation_keeps_control_identity_and_all_ordinary_causes() -> None:
    """Verify aggregation keeps control identity and all ordinary causes."""
    signal = KeyboardInterrupt("stop")
    first, second = ValueError("first"), OSError("second")
    assert combine_failures(signal, first) is signal
    assert signal.__cause__ is not None and signal.__cause__.__cause__ is first
    assert combine_failures(signal, second) is signal
    assert isinstance(signal.__cause__, LclErrorGroup)
    assert combine_failures(signal, signal) is signal
    with pytest.raises(LclValidationError):
        combine_failures(cast(BaseException, 1), second)


def test_native_groups_keep_splitting_members_codes_and_original_cause() -> None:
    """Callback groups retain their native causes and nested group topology."""
    native = ValueError("first")
    existing = LclValidationError("known", code="APP")
    original = ExceptionGroup("callback", [native, ExceptionGroup("nested", [existing])])
    wrapped = wrap_failure(original, LclError, "CALLBACK", span=UNKNOWN_SPAN)
    assert isinstance(wrapped, LclErrorGroup) and wrapped.__cause__ is original
    assert wrapped.code == "CALLBACK" and wrapped.span is UNKNOWN_SPAN
    assert wrapped.exceptions[0].__cause__ is native
    nested = wrapped.exceptions[1]
    assert isinstance(nested, LclErrorGroup) and nested.exceptions == (existing,)
    matched, remainder = wrapped.split(LclValidationError)
    assert isinstance(matched, LclErrorGroup) and isinstance(remainder, LclErrorGroup)
    with pytest.raises(LclErrorGroup) as caught:

        @guard_failure(LclError, "CALLBACK")
        def callback() -> None:
            raise original

        callback()
    assert caught.value.__cause__ is original


def test_control_group_keeps_native_protocol_and_identity() -> None:
    """Iterator signals inside a native group prevent ordinary group conversion."""
    original = ExceptionGroup("signals", [StopIteration(), ValueError("ordinary")])
    with pytest.raises(ExceptionGroup) as caught:

        @guard_failure(LclError, "CALLBACK")
        def callback() -> None:
            raise original

        callback()
    assert caught.value is original
    with pytest.raises(ExceptionGroup) as direct:
        wrap_failure(original, LclError, "CALLBACK")
    assert direct.value is original
