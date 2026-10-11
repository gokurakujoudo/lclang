"""Behavioural tests for live process-environment access."""

import pytest

from lclang.error import LclAttributeError, LclValidationError
from lclang.utils import env


def test_python_environment_reads_are_live_and_optional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Attribute and get access observe current process state without mutation."""
    name = "LCLANG_ENV_LIVE_TEST"
    invalid = "LCLANG-ENV-INVALID"
    monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(invalid, raising=False)
    assert getattr(env, name) is None
    private_name = "__missing__"
    with pytest.raises(LclAttributeError):
        getattr(env, private_name)
    assert env.get(name) is None
    assert env.get(invalid, "fallback") == "fallback"
    monkeypatch.setenv(name, "first")
    monkeypatch.setenv(invalid, "second")
    assert getattr(env, name) == "first"
    assert env.get(invalid) == "second"
    monkeypatch.setenv(name, "changed")
    assert getattr(env, name) == "changed"
    with pytest.raises(LclValidationError):
        env.get(1)  # type: ignore[arg-type]
