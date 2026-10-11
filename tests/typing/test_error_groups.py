"""Strict checker contracts for the shared native and LCL group interface."""

import pytest

from lclang.error import LclError, LclErrorGroup, LclValidationError


class DiagnosticGroup(ExceptionGroup[Exception], LclError):
    """A downstream subtype inherits compatible read-only message definitions."""


def test_group_message_and_derivation_keep_both_interfaces() -> None:
    """Native grouping and LCL diagnostics expose the same message and members."""
    member = LclError("member", code="APP/MEMBER")
    group = LclErrorGroup("combined", [member], code="APP/GROUP")
    ordinary: LclError = group
    native: BaseExceptionGroup[BaseException] = group
    assert ordinary.message == native.message == "combined"
    derived = group.derive([member])
    assert isinstance(derived, LclErrorGroup)
    assert derived.message == group.message and derived.code == group.code
    assert derived.exceptions == (member,)


def test_native_derive_preserves_the_supplied_exception_type() -> None:
    """The inherited generic protocol retains member identities when called directly."""
    group = LclErrorGroup("combined", [LclError("initial")], code="APP/GROUP")
    member = ValueError("selected")
    derived: ExceptionGroup[ValueError] = group.derive([member])
    assert isinstance(derived, LclErrorGroup)
    assert derived.exceptions == (member,) and derived.exceptions[0] is member
    assert derived.code == "APP/GROUP" and derived.message == "combined"


@pytest.mark.parametrize("control", [SystemExit(3), StopAsyncIteration("stop")])
def test_base_group_interface_rejects_controls_without_changing_original(
    control: BaseException,
) -> None:
    """A native base-group signature does not admit control signals into LCL groups."""
    member = LclError("member")
    group = LclErrorGroup("combined", [member], code="APP/GROUP")
    native: BaseExceptionGroup[BaseException] = group
    with pytest.raises(LclValidationError) as caught:
        native.derive([control])
    assert caught.value.code == "LCL021111"
    assert group.exceptions == (member,) and group.code == "APP/GROUP"
