"""Executable unit cases for the Modules-and-Frames tutorial."""

from tests.tutorials.support import execute_tutorial


def test_modules_and_frames_examples() -> None:
    """Reusable policy and hierarchical lookup match the documented results."""
    execute_tutorial("02-modules-and-frames.md", 2)

