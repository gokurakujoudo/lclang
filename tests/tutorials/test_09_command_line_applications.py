"""Executable unit cases for the command-line-applications tutorial."""

from tests.tutorials.support import execute_tutorial


def test_command_line_application_examples() -> None:
    """CLI defaults, config, overrides, and dry-run output remain deterministic."""
    execute_tutorial("09-command-line-applications.md", 2)

