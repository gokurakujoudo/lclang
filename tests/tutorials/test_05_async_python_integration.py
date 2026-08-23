"""Executable unit cases for the async-Python-integration tutorial."""

from tests.tutorials.support import execute_tutorial


def test_async_python_integration_examples() -> None:
    """Lazy calls and async context management follow documented event order."""
    execute_tutorial("05-async-python-integration.md", 2)

