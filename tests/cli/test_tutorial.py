"""Executable acceptance tests for the CLI tutorial."""

from pathlib import Path

import pytest

# Repository root containing the published tutorial.
ROOT = Path(__file__).resolve().parents[2]


def executable_example(text: str) -> str:
    """Extract the Python block explicitly marked for execution.

    :param text: Complete tutorial Markdown.
    :returns: Python source inside the marked fence.
    """
    marker = "<!-- lclang-cli-exec -->"
    marked = text.split(marker, 1)[1]
    return marked.split("```python", 1)[1].split("```", 1)[0].strip()


@pytest.mark.parametrize(
    "tutorial_path",
    [ROOT / "docs" / "tutorials" / "cli.md", ROOT / "docs" / "zh" / "cli.md"],
)
def test_cli_tutorial_script_executes_with_documented_output(
    tutorial_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each tutorial's complete user script runs and returns its asserted status."""
    tutorial = tutorial_path.read_text(encoding="utf-8")
    source = executable_example(tutorial)
    namespace = {"__name__": "lclang_cli_tutorial"}
    exec(compile(source, "<cli-tutorial>", "exec"), namespace)
    assert capsys.readouterr().out == "Hello from lclang (as of 2026-08-09)\n"
