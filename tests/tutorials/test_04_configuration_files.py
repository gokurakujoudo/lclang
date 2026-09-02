"""Executable unit cases for the configuration-files tutorial."""

from tests.tutorials.support import execute_tutorial


def test_configuration_file_examples() -> None:
    """Parsing, composition, and reusable config Frames produce stated results."""
    execute_tutorial("04-configuration-files.md", 5)

