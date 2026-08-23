"""Executable unit cases for the LCL-language tutorial."""

from tests.tutorials.support import execute_tutorial


def test_language_examples() -> None:
    """Safe access, transformations, and canonical syntax remain executable."""
    execute_tutorial("03-language.md", 3)

