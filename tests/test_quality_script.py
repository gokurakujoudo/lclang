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

    def test_imports_and_docstrings_do_not_consume_the_source_budget(self) -> None:
        """The line gate measures implementation rather than imports or documentation."""
        imports = "\n".join(f"import module_{index}" for index in range(210))
        documentation = '\n'.join(['"""Module', *["detail" for _ in range(210)], '"""'])
        source = f"{documentation}\n{imports}\nvalue = 1\n"
        self.assertEqual(check_source(source, DISPLAY_PATH), [])

    def test_expression_bodies_do_not_confuse_docstring_exclusion(self) -> None:
        """Lambda bodies remain ordinary counted implementation expressions."""
        source = '"""Module."""\n\nvalue = lambda item: item\n'
        self.assertEqual(check_source(source, DISPLAY_PATH), [])

    def test_incomplete_rst_fields_are_reported_independently(self) -> None:
        """Missing parameter, result, and exception fields are visible."""
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

    def test_none_return_and_ordinary_behavior_need_no_redundant_fields(self) -> None:
        """None-returning callables need neither a result field nor a forced note."""
        source = '''"""Module."""

def action(value: str) -> None:
    """Consume one value.

    :param value: Text consumed by the action.
    """
    print(value)
'''
        self.assertEqual(check_source(source, DISPLAY_PATH), [])

    def test_reraised_exception_variables_do_not_invent_exception_types(self) -> None:
        """A dynamic re-raise cannot produce a meaningful rST exception type field."""
        source = '''"""Module."""

def reraised(error: Exception) -> None:
    """Raise a caller-provided failure.

    :param error: Failure selected by the caller.
    """
    raise error
'''
        self.assertEqual(check_source(source, DISPLAY_PATH), [])

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
