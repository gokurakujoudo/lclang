"""Executable unit cases for the caching-and-recalculation tutorial."""

from tests.tutorials.support import execute_tutorial


def test_caching_and_recalculation_examples() -> None:
    """Single-flight caching and targeted refresh retain snapshot semantics."""
    execute_tutorial("06-caching-and-recalculation.md", 2)

