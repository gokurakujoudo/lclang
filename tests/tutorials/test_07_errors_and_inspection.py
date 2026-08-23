"""Executable unit cases for the errors-and-inspection tutorial."""

from tests.tutorials.support import execute_tutorial


def test_errors_and_inspection_examples() -> None:
    """Structured failures and non-evaluating inspection expose stated evidence."""
    execute_tutorial("07-errors-and-inspection.md", 2)

