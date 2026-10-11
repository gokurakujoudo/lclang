"""CLI runtime tree output is opt-in and value stdout remains compatible."""

import asyncio

import pytest

from lclang.cli.builtin_command import LCLANG_CLI_ENTRANCE


def test_eval_tree_is_explicit_and_contains_actual_dependencies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same calculation can produce either its value or its observed tree."""
    argv = [
        "python",
        "__main__.py",
        "eval_lcl",
        "-o",
        "RESULT",
        "LCL[b + a]",
        "-o",
        "a",
        "2",
        "-o",
        "b",
        "3",
    ]
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run(argv)) == 0
    assert capsys.readouterr().out == "32\n"
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run([*argv, "-o", "TREE"])) == 0
    output = capsys.readouterr().out
    assert "RESULT: b + a (" in output
    assert "├─ a: (str) '2' (external)" in output
    assert "└─ b: (str) '3' (external)" in output
