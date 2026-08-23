"""Executable unit cases for the production-patterns tutorial."""

from tests.tutorials.support import execute_tutorial


def test_production_pattern_examples() -> None:
    """Factories, scenarios, limits, and error boundaries behave as documented."""
    execute_tutorial("12-production-patterns.md", 2)

