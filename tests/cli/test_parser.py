"""Behavioural tests for full argv and common options."""

from datetime import date

import pytest

from lclang.ast import LclConstant, LclName
from lclang.cli.parser import (
    help_requested,
    lazy_override_expression,
    override_expression,
    parse_cli_params,
    parse_common_options,
    split_argv,
)
from lclang.errors import LclCliUsageError


def test_parser_accepts_aliases_last_override_and_dates() -> None:
    """Full argv becomes immutable params with right-biased override values."""
    parts = split_argv(
        [
            "C:/Python/python.exe",
            "tool.py",
            "run",
            "-c",
            "settings.lclcfg",
            "-o",
            "count",
            "1",
            "--override",
            "count",
            "LCL[base + 1]",
            "--as-of",
            "20260809",
            "--dryrun",
            "--verbose",
        ]
    )
    params = parse_cli_params(parts, ("run",), parts.tokens[1:])
    assert params.executable_path == "C:/Python/python.exe"
    assert params.command == ("run",)
    assert params.as_of_date == date(2026, 8, 9)
    assert params.dryrun is True
    assert params.verbose is True
    assert params.config_file_path == "settings.lclcfg"
    assert params.overrides == {"count": "LCL[base + 1]"}


def test_override_without_value_is_true_and_never_consumes_an_override_option() -> None:
    """A following override starts a new binding while other tokens remain values."""
    parsed = parse_common_options(
        [
            "-o",
            "first",
            "-o",
            "second",
            "value",
            "--override",
            "third",
            "--override",
            "fourth",
            "-h",
            "-o",
            "first",
            "final",
        ]
    )
    assert parsed.overrides == {
        "first": "final",
        "second": "value",
        "third": True,
        "fourth": "-h",
    }
    assert parsed.help_requested is False
    assert parse_common_options(["-o", "EVAL"]).overrides == {"EVAL": True}


@pytest.mark.parametrize(
    "argv, message",
    [
        (["python", "tool", "run"], ".py"),
        (["python", "tool.py", "run", "-a", "20260230"], "date"),
        (["python", "tool.py", "run", "-o", "dryrun", "yes"], "reserved"),
        (["python", "tool.py", "run", "--unknown"], "unknown"),
    ],
)
def test_parser_reports_practical_usage_errors(argv: list[str], message: str) -> None:
    """Malformed boundaries, dates, keys, and options are typed usage errors."""
    with pytest.raises(LclCliUsageError, match=message):
        parts = split_argv(argv)
        parse_cli_params(parts, ("run",), parts.tokens[1:])


@pytest.mark.parametrize(
    "tokens, message",
    [
        (["-wif", "--dryrun"], "duplicate dryrun"),
        (["--verbose", "--verbose"], "duplicate verbose"),
        (["-c"], "missing option value"),
        (["-c", "a", "--config", "b"], "duplicate config"),
        (["-a", "20260809", "--as-of", "20260810"], "duplicate as-of"),
        (["-o"], "missing override key"),
        (["-o", "bad-key", "x"], "identifier"),
    ],
)
def test_common_parser_rejects_duplicate_and_arity_errors(
    tokens: list[str],
    message: str,
) -> None:
    """Every fixed-arity and singleton error remains deterministic."""
    with pytest.raises(LclCliUsageError, match=message):
        parse_common_options(tokens)


def test_help_boundaries_and_override_classification() -> None:
    """Help skips value slots and only valid whole markers become expressions."""
    assert help_requested(["-c", "-h"]) is False
    assert help_requested(["-c", "file", "--help"]) is True
    assert help_requested(["-o", "x", "-h"]) is False
    assert help_requested(["-o", "x", "-o", "y", "-h"]) is False
    assert help_requested(["--unknown", "-h"]) is True
    assert isinstance(override_expression("literal"), LclConstant)
    assert isinstance(override_expression("LCL[]"), LclConstant)
    assert isinstance(override_expression("LCL[bad +]"), LclConstant)
    assert isinstance(override_expression("LCL[value]"), LclName)
    assert lazy_override_expression("literal") is None
    assert lazy_override_expression("LCL[]") is None
    assert lazy_override_expression("LCL[bad +]") is None
    assert isinstance(lazy_override_expression("LCL[value]"), LclName)
    assert isinstance(lazy_override_expression("LCL['literal']"), LclConstant)
    assert parse_common_options(["-h"]).help_requested is True
    assert parse_common_options(["--verbose", "-o", "flag"]).verbose is True
    literal_verbose = parse_common_options(["-o", "value", "--verbose"])
    assert literal_verbose.verbose is False
    assert literal_verbose.overrides == {"value": "--verbose"}


def test_process_argv_adaptation_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ambient argv is snapshotted and invalid full argv shapes are rejected."""
    monkeypatch.setattr("sys.argv", ["ambient.py", "run"])
    parts = split_argv()
    assert parts.script_label == "ambient.py"
    assert parts.tokens == ("run",)
    with pytest.raises(LclCliUsageError, match="requires"):
        split_argv(["python"])
    with pytest.raises(LclCliUsageError, match="non-empty"):
        split_argv(["python", "tool.py", ""])
