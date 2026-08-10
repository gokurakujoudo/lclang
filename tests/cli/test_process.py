"""Behavioural tests for explicit and ambient Python-script argv adaptation."""

import sys

import pytest

from pylcl.cli.process import split_argv
from pylcl.errors import LclCliUsageError


def test_ambient_process_arguments_are_snapshotted_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ambient adaptation prepends the interpreter and retains current script tokens."""
    monkeypatch.setattr(sys, "argv", ["folder/sample.py", "admin", "show"])
    parts = split_argv()
    assert parts.executable_path == sys.executable
    assert parts.script_path == "folder/sample.py"
    assert parts.tokens == ("admin", "show")


@pytest.mark.parametrize(
    "values",
    [
        ["python"],
        ["python", "sample"],
        ["python", "sample.py", ""],
        ["python", 1, "show"],
    ],
)
def test_invalid_full_argv_is_rejected(values: list[object]) -> None:
    """Incomplete, non-script, empty, and non-text tokens are usage failures."""
    with pytest.raises(LclCliUsageError):
        split_argv(values)  # type: ignore[arg-type]
