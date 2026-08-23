"""Executable unit cases for the dependency-analysis tutorial."""

from tests.tutorials.support import execute_tutorial


def test_dependency_analysis_examples() -> None:
    """Static graphs and runtime reconciliation produce the documented evidence."""
    execute_tutorial("08-dependency-analysis.md", 3)

