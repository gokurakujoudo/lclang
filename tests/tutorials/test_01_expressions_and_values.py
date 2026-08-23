"""Executable unit cases for the expressions-and-values tutorial."""

from tests.tutorials.support import execute_tutorial


def test_expressions_and_values_examples() -> None:
    """The three progressively richer expression examples produce their results."""
    execute_tutorial("01-expressions-and-values.md", 3)

