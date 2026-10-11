"""Python utilities work without loading any LCL language implementation."""

import subprocess
import sys
from pathlib import Path


def test_utilities_and_their_failures_do_not_load_language() -> None:
    """A fresh interpreter uses utility values and diagnostics with language imports blocked."""
    source = """
import asyncio
import importlib.abc
import sys

class RejectLanguage(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "lclang.lang" or fullname.startswith("lclang.lang."):
            raise AssertionError("utility imported language: " + fullname)
        return None

sys.meta_path.insert(0, RejectLanguage())
from lclang.error import LclValidationError, LclUtilityError
from lclang.utils import DefaultBinding, env, invoke, normalize_masked_mapping, parse_ymd, to_ymd
from lclang.utils.calendar.factories.selected_date_calendar import at

assert to_ymd(parse_ymd("20260102")) == "20260102"
assert str(at("20260102").calendar_id) == "at(20260102)"
assert env.get("LCLANG_DOES_NOT_EXIST_IN_THIS_TEST", "fallback") == "fallback"
values, masks = normalize_masked_mapping({"token!": "secret"})
assert values == {"token": "secret"} and masks == frozenset({"token"})
for operation, code in [
    (lambda: DefaultBinding(value=None, factory=list), "LCL781161"),
    (lambda: normalize_masked_mapping({"token": 1, "token!": 2}), "LCL851231"),
    (lambda: parse_ymd("20260230"), "LCL941221"),
]:
    try:
        operation()
    except LclValidationError as error:
        assert error.code == code, (error.code, code)
        assert code in str(error)
    else:
        raise AssertionError("expected utility validation")

def fail():
    raise OSError("callback failed")

async def main():
    try:
        await invoke(fail)
    except LclUtilityError as error:
        assert error.code == "LCL771811"
        assert isinstance(error.__cause__, OSError)
        assert "callback failed" in str(error)
    else:
        raise AssertionError("expected callback failure")

asyncio.run(main())
assert not any(name == "lclang.lang" or name.startswith("lclang.lang.") for name in sys.modules)
print("independent utilities passed")
"""
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=root, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "independent utilities passed\n"
