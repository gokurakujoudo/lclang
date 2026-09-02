"""Executable contracts for the downstream Python utilities tutorial."""

from tests.tutorials.support import execute_tutorial


def test_python_utility_examples() -> None:
    """Environment, logging, stdlib, and calendar utilities work as published."""
    execute_tutorial("16-python-utilities.md", 4)
