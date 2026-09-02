"""Executable contracts for tutorial chapter 13."""

from tests.tutorials.support import execute_tutorial


def test_scoped_values_and_frame_evaluation_tutorial() -> None:
    """Every complete scoped-values example runs exactly as published."""
    execute_tutorial("13-scoped-values-and-frame-evaluation.md", 7)
