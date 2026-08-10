"""Behavioural tests for the executable lclang CLI module entrance."""

import asyncio
import os
import runpy
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang import __version__
from lclang.cli.application import LCLANG_CLI_ENTRANCE
from lclang.cli.builtin_docs import render_builtin_docs

# Full argv prefix used by in-process module entrance cases.
MODULE_ARGV = ("python", "__main__.py")

# Valid fixed-point combinator used by the screenshot-shaped regression.
Z_OVERRIDE = (
    "LCL[(f) -> ((x) -> f((*args) -> x(x)(*args)))"
    "((x) -> f((*args) -> x(x)(*args)))]"
)
# Deliberately incomplete quicksort marker: the final Z-call parenthesis is absent.
MALFORMED_QUICKSORT_OVERRIDE = (
    "LCL[Z((again) -> (items) -> [] if not items else "
    "[*again([item for item in items[1:] if item < items[0]]), items[0], "
    "*again([item for item in items[1:] if item >= items[0]])]]"
)


def test_parse_lcl_renders_a_non_evaluating_static_result_tree(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Static inspection preserves ordered literal leaves and unsafe expressions."""
    literal_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [*MODULE_ARGV, "parse_lcl", "-o", "RESULT", "100"]
        )
    )
    assert literal_status == 0
    assert capsys.readouterr().out == (
        "- RESULT@cli_runtime/cli_overrides: (ExternalProvided) str: '100'\n"
    )

    malformed_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [*MODULE_ARGV, "parse_lcl", "-o", "RESULT", "LCL[bad +]"]
        )
    )
    assert malformed_status == 0
    assert capsys.readouterr().out == (
        "- RESULT@cli_runtime/cli_overrides: (ExternalProvided) str: 'LCL[bad +]'\n"
    )

    lazy_constant_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [*MODULE_ARGV, "parse_lcl", "-o", "RESULT", "LCL['100']"]
        )
    )
    assert lazy_constant_status == 0
    assert "'100' (NotEvaluated) NoneType: None" in capsys.readouterr().out

    status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [
                *MODULE_ARGV,
                "parse_lcl",
                "-o",
                "a",
                "100",
                "-o",
                "b",
                "200",
                "-o",
                "RESULT",
                "LCL[a+b]",
            ]
        )
    )
    assert status == 0
    lines = capsys.readouterr().out.splitlines()
    assert "RESULT@" in lines[0]
    assert "a + b (NotEvaluated)" in lines[0]
    assert "a@cli_overrides: (ExternalProvided) str: '100'" in lines[1]
    assert "b@cli_overrides: (ExternalProvided) str: '200'" in lines[2]

    unsafe_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [*MODULE_ARGV, "parse_lcl", "-o", "RESULT", "LCL[1 / 0 + missing]"]
        )
    )
    assert unsafe_status == 0
    unsafe_output = capsys.readouterr().out
    assert "1 / 0 + missing (NotEvaluated)" in unsafe_output
    assert "missing@" in unsafe_output
    assert "LclNameError" in unsafe_output

    native_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [
                *MODULE_ARGV,
                "parse_lcl",
                "-o",
                "a",
                "items",
                "-o",
                "RESULT",
                "LCL[len(a) + iter.first([a])]",
            ]
        )
    )
    assert native_status == 0
    native_output = capsys.readouterr().out
    assert "len@" in native_output and "(NativeProvided)" in native_output
    assert "iter@" in native_output
    assert "Builtin Function: len" in native_output
    assert "Builtin Namespace: iter" in native_output
    assert "a@cli_overrides: (ExternalProvided) str: 'items'" in native_output
    assert "mappingproxy" not in native_output
    assert "0x" not in native_output


def test_builtins_command_prints_the_reviewed_inventory(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command returns the complete renderer output without parameters."""
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run([*MODULE_ARGV, "builtins"])) == 0
    captured = capsys.readouterr()
    assert captured.out == f"{render_builtin_docs()}\n"
    assert captured.err == ""
    assert asyncio.run(
        LCLANG_CLI_ENTRANCE.run([*MODULE_ARGV, "builtins", "-h"])
    ) == 0
    help_output = capsys.readouterr().out
    assert "List canonical LCL builtins" in help_output


def test_eval_lcl_returns_string_values_and_maps_usage_and_evaluation_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Literal overrides concatenate while missing and failing results use status two."""
    status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [
                *MODULE_ARGV,
                "eval_lcl",
                "-o",
                "a",
                "100",
                "-o",
                "b",
                "200",
                "-o",
                "RESULT",
                "LCL[a+b]",
            ]
        )
    )
    assert status == 0
    assert capsys.readouterr().out == "100200\n"

    assert asyncio.run(LCLANG_CLI_ENTRANCE.run([*MODULE_ARGV, "eval_lcl"])) == 2
    assert "missing required parameter: RESULT" in capsys.readouterr().err
    assert asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [*MODULE_ARGV, "eval_lcl", "-o", "RESULT", "LCL[1 / 0]"]
        )
    ) == 2
    assert "division by zero" in capsys.readouterr().err


def test_parse_lcl_eval_flag_renders_success_and_failure_cache_trees(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Valueless EVAL opts into cached inspection without losing failed trees."""
    assert asyncio.run(
        LCLANG_CLI_ENTRANCE.run([*MODULE_ARGV, "parse_lcl", "-h"])
    ) == 0
    eval_help = capsys.readouterr().out
    assert "EVAL" in eval_help
    assert "default=False" in eval_help

    success_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [
                *MODULE_ARGV,
                "parse_lcl",
                "-o",
                "base",
                "LCL[1 + 1]",
                "-o",
                "RESULT",
                "LCL[base + 1]",
                "-o",
                "EVAL",
            ]
        )
    )
    assert success_status == 0
    success_lines = capsys.readouterr().out.splitlines()
    assert "RESULT@" in success_lines[0]
    assert "(Cached) int: 3" in success_lines[0]
    assert "base@cli_overrides: 1 + 1 (Cached) int: 2" in success_lines[1]

    failure_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [
                *MODULE_ARGV,
                "parse_lcl",
                "-o",
                "EVAL",
                "-o",
                "RESULT",
                "LCL[1 / 0]",
            ]
        )
    )
    assert failure_status == 0
    failure_output = capsys.readouterr().out
    assert "RESULT@" in failure_output
    assert "(Cached) LclEvaluationError:" in failure_output
    assert "division by zero" in failure_output
    assert "[variable evaluation stack: RESULT]" in failure_output

    eval_status = asyncio.run(
        LCLANG_CLI_ENTRANCE.run(
            [*MODULE_ARGV, "eval_lcl", "-o", "RESULT", "100", "-o", "EVAL"]
        )
    )
    assert eval_status == 0
    assert capsys.readouterr().out == "100\n"


def test_eval_lcl_reports_malformed_override_and_lexical_variable_stacks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Malformed screenshot input and valid closure failures identify their owners."""
    malformed_args = [
        *MODULE_ARGV,
        "eval_lcl",
        "-o",
        "Z",
        Z_OVERRIDE,
        "-o",
        "quicksort",
        MALFORMED_QUICKSORT_OVERRIDE,
        "-o",
        "RESULT",
        "LCL[quicksort([7, 2, 9, 2, -1, 5])]",
    ]
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run(malformed_args)) == 2
    malformed_error = capsys.readouterr().err
    assert "TypeError: 'str' object is not callable" in malformed_error
    assert "[variable evaluation stack: RESULT]" in malformed_error

    parse_args = [*malformed_args]
    parse_args[2] = "parse_lcl"
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run(parse_args)) == 0
    parse_output = capsys.readouterr().out
    assert "quicksort@cli_overrides: (ExternalProvided) str:" in parse_output

    valid_failure_args = [
        *MODULE_ARGV,
        "eval_lcl",
        "-o",
        "quicksort",
        "LCL[(items) -> 1 / 0]",
        "-o",
        "RESULT",
        "LCL[quicksort([1])]",
    ]
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run(valid_failure_args)) == 2
    valid_error = capsys.readouterr().err
    assert "division by zero" in valid_error
    assert "[variable evaluation stack: RESULT -> quicksort]" in valid_error


def test_module_help_version_and_real_subprocess_are_deterministic(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The installed-style module owns built-ins and runs opaque Unicode tokens."""
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run([*MODULE_ARGV, "-h"])) == 0
    help_output = capsys.readouterr().out
    assert "parse_lcl" in help_output
    assert "eval_lcl" in help_output
    assert "builtins" in help_output
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run([*MODULE_ARGV, "-v"])) == 0
    assert capsys.readouterr().out == f"__main__.py {__version__}\n"

    monkeypatch.setattr(
        sys,
        "argv",
        ["__main__.py", "eval_lcl", "-o", "RESULT", "ambient"],
    )
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("lclang.cli.__main__", run_name="__main__")
    assert stopped.value.code == 0
    assert capsys.readouterr().out == "ambient\n"
    imported = runpy.run_module("lclang.cli.__main__", run_name="lclang_cli_probe")
    assert imported["LCLANG_CLI_ENTRANCE"] is LCLANG_CLI_ENTRANCE
    assert capsys.readouterr().out == ""

    with TemporaryDirectory() as directory:
        root = Path(directory)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        environment["PYTHONIOENCODING"] = "utf-8"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "lclang.cli",
                "eval_lcl",
                "-o",
                "left",
                "值",
                "-o",
                "right",
                "--literal",
                "-o",
                "RESULT",
                "LCL[left + right]",
            ],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert completed.returncode == 0
        assert completed.stdout == "值--literal\n"
        assert completed.stderr == ""
        assert list(root.iterdir()) == []

        builtin_process = subprocess.run(
            [sys.executable, "-m", "lclang.cli", "builtins"],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert builtin_process.returncode == 0
        assert builtin_process.stdout == f"{render_builtin_docs()}\n"
        assert builtin_process.stderr == ""
        assert list(root.iterdir()) == []
