"""Executable acceptance tests for the workflow-status tutorial."""

from pathlib import Path

# Repository root containing the published tutorial.
ROOT = Path(__file__).resolve().parents[2]


def executable_examples(text: str) -> list[str]:
    """Extract every explicitly executable Python example.

    :param text: Complete workflow tutorial Markdown.
    :returns: Python sources following each execution marker.
    """
    marker = "<!-- pylcl-workflow-exec -->"
    return [
        part.split("```python", 1)[1].split("```", 1)[0].strip()
        for part in text.split(marker)[1:]
    ]


def test_workflow_tutorial_examples_execute() -> None:
    """The successful and exceptional examples match the implemented contract."""
    path = ROOT / "docs" / "tutorials" / "workflow-status.md"
    examples = executable_examples(path.read_text(encoding="utf-8"))
    assert len(examples) == 2
    for source in examples:
        exec(compile(source, "<workflow-status-tutorial>", "exec"), {})

