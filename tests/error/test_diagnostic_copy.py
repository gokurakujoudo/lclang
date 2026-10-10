"""Typed diagnostic state copying without instance dictionary introspection."""

from copy import copy
from datetime import date
from typing import Any, Self, cast

import pytest

from lclang.cli import CommandGroup
from lclang.common.source_location import UNKNOWN_SPAN
from lclang.error import (
    CalendarCannotLoadException,
    CalendarLogicException,
    ConfigLoadFrame,
    DateOperationOutOfScopeException,
    EscapeDecodeError,
    FStringScanError,
    InternalLiteralScanError,
    LclError,
    LclErrorGroup,
    LclValidationError,
    RouteFailure,
)
from lclang.utils.calendar import ALL_DAYS, CalendarID


class GuardedError(LclError):
    """Reject dictionary access so copying must use the declared fields."""

    def __getattribute__(self, name: str) -> Any:
        """Permit ordinary fields and reject dictionary reflection."""
        if name == "__dict__":
            raise AssertionError("diagnostic copying accessed an instance dictionary")
        return super().__getattribute__(name)


class GuardedGroup(LclErrorGroup):
    """Reject dictionary access during group allocation and splitting."""

    def __getattribute__(self, name: str) -> Any:
        """Permit group fields and reject dictionary reflection."""
        if name == "__dict__":
            raise AssertionError("group copying accessed an instance dictionary")
        return super().__getattribute__(name)


def test_copy_retains_declared_state_without_reading_dictionary() -> None:
    """Codes, stacks, args, causes, notes and concrete types survive a copy."""
    original = GuardedError("known failure", code="APP/COPY", variable_stack=("entry",))
    original.__cause__ = OSError("native")
    original.add_note("original note")
    original.masked = True
    detached = copy(original)
    assert type(detached) is GuardedError and detached is not original
    assert detached.code == "APP/COPY" and detached.message == original.message
    assert detached.args == original.args and detached.variable_stack == ("entry",)
    assert detached.__cause__ is original.__cause__ and detached.masked
    detached.add_note("copy note")
    assert original.__notes__ == ["original note"]
    assert detached.__notes__ == ["original note", "copy note"]


def test_group_allocation_and_split_keep_selected_arguments_without_dictionary() -> None:
    """Native ExceptionGroup state agrees with its selected member objects."""
    first = LclValidationError("first", code="APP/FIRST")
    second = LclError("second", code="APP/SECOND")
    group = GuardedGroup("multiple", [first, second], code="APP/GROUP")
    group.add_note("group note")
    selected, remaining = group.split(LclValidationError)
    assert isinstance(selected, GuardedGroup) and isinstance(remaining, GuardedGroup)
    assert selected.exceptions == (first,) and remaining.exceptions == (second,)
    assert selected.args[1] == [first] and remaining.args[1] == [second]
    selected.add_note("selected")
    assert group.__notes__ == ["group note"]
    assert remaining.__notes__ == ["group note"]
    detached = copy(group)
    assert isinstance(detached, GuardedGroup) and detached.exceptions == group.exceptions
    assert detached.code == group.code and detached.message == group.message


def test_validation_has_an_explicit_empty_conflict_field() -> None:
    """Ordinary validation diagnostics expose an empty typed conflict tuple."""
    failure = LclValidationError("invalid field", code="APP/VALIDATION")
    assert failure.binding_names == ()


@pytest.mark.parametrize(
    "failure,fields",
    [
        (
            DateOperationOutOfScopeException(date(2026, 1, 1), ALL_DAYS),
            ("source_date", "source_calendar"),
        ),
        (CalendarCannotLoadException(CalendarID("example")), ("calendar_id",)),
        (CalendarLogicException(CalendarID("example")), ("calendar_id",)),
        (EscapeDecodeError("escape", 3, code="APP"), ("end",)),
        (InternalLiteralScanError("literal", 4, code="APP"), ("end",)),
        (FStringScanError("fstring", 5, code="APP"), ("end",)),
        (
            RouteFailure("route", CommandGroup("root", "Root", []), ("nested",), code="APP"),
            ("group", "path"),
        ),
    ],
)
def test_specialized_copy_retains_fields_and_independent_loading_context(
    failure: LclError, fields: tuple[str, ...]
) -> None:
    """A copied diagnostic retains specialized data and detached propagation state."""
    failure.span = UNKNOWN_SPAN
    failure.native_cause = "OSError: original"
    failure.__cause__ = OSError("original")
    failure.__context__ = ValueError("context")
    failure.__suppress_context__ = True
    failure.add_note("original")
    try:
        raise failure
    except LclError:
        detached = failure.derive_config_context(ConfigLoadFrame(UNKNOWN_SPAN.origin))
    assert type(detached) is type(failure)
    assert detached.args == failure.args and detached.span is UNKNOWN_SPAN
    assert detached.__cause__ is failure.__cause__ and detached.__context__ is failure.__context__
    assert detached.__suppress_context__ and detached.__traceback__ is failure.__traceback__
    assert detached.native_cause == failure.native_cause
    assert failure.config_stack == () and len(detached.config_stack) == 1
    assert all(getattr(detached, name) is getattr(failure, name) for name in fields)
    detached.add_note("copy")
    assert failure.__notes__ == ["original"]


def test_application_copy_hook_retains_declared_business_fields() -> None:
    """Application subtypes can retain their fields without repeating constructors."""

    class BusinessError(GuardedError):
        def __init__(self, account: str) -> None:
            super().__init__("account failed", code="APP/ACCOUNT")
            self.account = account

        def copy_diagnostic_fields(self, target: LclError) -> None:
            super().copy_diagnostic_fields(target)
            copied = cast(Self, target)
            copied.account = self.account

    failure = BusinessError("account-42")
    detached = copy(failure)
    assert detached.account == "account-42" and detached.code == "APP/ACCOUNT"


def test_copy_hook_rejects_incompatible_target_and_retains_conflict_metadata() -> None:
    """Wrong targets fail safely, while declared conflict names survive copying."""
    failure = LclValidationError("conflict", code="APP")
    failure.binding_names = ("scope", "scope.item")
    assert copy(failure).binding_names == failure.binding_names
    with pytest.raises(LclValidationError) as wrong_type:
        failure.copy_diagnostic_fields(cast(LclValidationError, object()))
    assert wrong_type.value.code == "LCL011183"
    with pytest.raises(LclValidationError) as wrong_family:
        failure.copy_diagnostic_fields(cast(LclValidationError, LclError("plain", code="APP")))
    assert wrong_family.value.code == "LCL011183"
