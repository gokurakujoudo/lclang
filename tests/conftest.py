"""Deterministic project-wide property-test configuration."""

import pytest
from hypothesis import settings

settings.register_profile(
    "lclang",
    max_examples=300,
    derandomize=True,
    database=None,
    deadline=None,
)
settings.load_profile("lclang")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark documentation and release tests for coverage-independent execution.

    :param items: Collected pytest items to classify by owning path.
    :returns: ``None``.
    """
    for item in items:
        path = item.path.as_posix()
        if "/tests/release/" in f"/{path}":
            item.add_marker(pytest.mark.release)
        elif "/tests/tutorials/" in f"/{path}" or item.path.name in {
            "test_documentation.py",
            "test_tutorial.py",
            "test_calendar_documentation.py",
        }:
            item.add_marker(pytest.mark.docs)
