"""Builtin numbering, documentation, and prevention of uncoded proactive failures."""

import re
from pathlib import Path

import pytest

from lclang.error import LclError, LclValidationError, get_error_code_path, get_error_codes
from lclang.error.codes.code_registry import CODE_ENUMS
from scripts.check_errors import check_error_contract, check_error_source


def test_registered_codes_have_unique_complete_classifications() -> None:
    """Verify registered codes have unique complete classifications."""
    codes = get_error_codes()
    assert codes == tuple(sorted(set(codes)))
    assert all(re.fullmatch(r"LCL[0-9]{6}", code) for code in codes)
    assert all(len(group) == len(group.__members__) for group in CODE_ENUMS)
    assert check_error_contract() == []
    assert get_error_code_path("LCL131421")[:5] == (
        "Language",
        "Evaluator",
        "Evaluate operators",
        "Arithmetic failure",
        "Arithmetic operation",
    )


def test_code_directory_covers_every_registered_identifier() -> None:
    """Verify code directory covers every registered identifier."""
    text = (Path(__file__).resolve().parents[2] / "docs/reference/errors.md").read_text(
        encoding="utf-8"
    )
    rows = re.findall(r"^\| `(LCL[0-9]{6})` \| (.+)$", text, re.MULTILINE)
    assert sorted(code for code, _ in rows) == list(get_error_codes())
    for code, payload in rows:
        fields = payload.split(" | ")
        assert len(fields) == 5, code
        assert all(field.strip(" |").strip() for field in fields), code
        assert " → ".join(get_error_code_path(code)) in fields[0]


def test_application_codes_and_invalid_registry_inputs_are_distinct() -> None:
    """Verify application codes and invalid registry inputs are distinct."""
    assert LclError("application failure", code="APP/42").code == "APP/42"
    with pytest.raises(LclValidationError) as missing:
        get_error_code_path("APP/42")
    assert missing.value.code == "LCL014211"
    with pytest.raises(LclValidationError) as wrong_type:
        get_error_code_path(1)  # type: ignore[arg-type]
    assert wrong_type.value.code == "LCL014111"


@pytest.mark.parametrize(
    "source,fragment",
    [
        ('raise ValueError("bad")', "native proactive failure"),
        ('raise RuntimeError("bad")', "native proactive failure"),
        ('raise KeyError("missing")', "native proactive failure"),
        ('raise ImportError("module")', "native proactive failure"),
        ("raise ValueError", "native proactive failure"),
        ('raise errors.TypeError("bad")', "native proactive failure"),
        ("assert ready", "ordinary assertions"),
        ('raise LclValidationError("bad")', "must specify its code"),
        ('raise errors.LclValidationError("bad")', "must specify its code"),
        (
            "from lclang.error import GeneralErrorCode\n"
            'raise LclError("bad", code=GeneralErrorCode.MISSING)',
            "unregistered builtin code",
        ),
    ],
)
def test_source_audit_rejects_unencoded_failures(source: str, fragment: str) -> None:
    """Verify source audit rejects unencoded failures."""
    assert fragment in check_error_source(source, Path("example.py"))[0]


def test_source_audit_preserves_protocols_and_application_code_parameters() -> None:
    """Verify source audit preserves protocols and application code parameters."""
    assert (
        check_error_source(
            "raise StopIteration\nraise asyncio.CancelledError()\n"
            'raise BaseExceptionGroup("signals", signals)\n'
            'raise LclError("message", code=code)',
            Path("example.py"),
        )
        == []
    )
