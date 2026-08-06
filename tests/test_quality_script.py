"""Behavioural tests for repository quality checks."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_project import check_source

DISPLAY_PATH = Path("example.py")


class QualityScriptTests(unittest.TestCase):
    """Verify source length and exhaustive production-docstring enforcement."""

    def test_short_documented_module_passes(self) -> None:
        """A short module with documented public objects must be accepted."""
        source = '''"""Module."""

def public(value: str) -> str:
    """Return a checked value.

    :param value: Candidate text.
    :returns: The unchanged non-empty value.
    :raises ValueError: If *value* is empty.

    .. note::
       Whitespace-only values are retained.
    """
    if not value:
        raise ValueError("empty")
    return value
'''
        self.assertEqual(check_source(source, DISPLAY_PATH), [])

    def test_long_or_undocumented_module_reports_both_failures(self) -> None:
        """Independent size and documentation failures must both be reported."""
        source = "def public() -> None:\n    pass\n" + "\n" * 199
        failures = check_source(source, DISPLAY_PATH)
        self.assertEqual(len(failures), 2)
        self.assertTrue(any("200 lines" in failure for failure in failures))
        self.assertTrue(any("docstring" in failure for failure in failures))

    def test_incomplete_rst_fields_are_reported_independently(self) -> None:
        """Missing parameter, result, exception, and note fields are visible."""
        source = '''"""Module."""

def public(value: str) -> str:
    """Return a value."""
    if not value:
        raise ValueError("empty")
    return value
'''
        failures = check_source(source, DISPLAY_PATH)
        assert any(":param value:" in failure for failure in failures)
        assert any(":returns:" in failure for failure in failures)
        assert any(":raises ValueError:" in failure for failure in failures)
        assert any(".. note::" in failure for failure in failures)

    def test_annotated_public_value_fields_require_param_entries(self) -> None:
        """Dataclass-like constructor fields are documented at the class."""
        source = '''"""Module."""

class Value:
    """Store a value.

    .. note::
       Instances are ordinary mutable values.
    """

    item: str
'''
        assert any(":param item:" in failure for failure in check_source(source, DISPLAY_PATH))

    def test_private_and_nested_declarations_use_the_same_contract(self) -> None:
        """Private helpers and nested functions cannot escape documentation checks."""
        source = '''"""Module."""

class _Private:
    item: str

    def _method(self, value: str) -> str:
        def nested(extra: str) -> str:
            return value + extra
        return nested(value)
'''
        failures = check_source(source, DISPLAY_PATH)
        assert any("_Private" in failure for failure in failures)
        assert any("_method" in failure for failure in failures)
        assert any("nested" in failure for failure in failures)
