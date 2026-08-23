"""Executable unit cases for the workflow-status tutorial."""

from tests.tutorials.support import execute_tutorial


def test_workflow_status_examples() -> None:
    """Successful, erroneous, and unfinished work aggregate as documented."""
    execute_tutorial("10-workflow-status.md", 2)

