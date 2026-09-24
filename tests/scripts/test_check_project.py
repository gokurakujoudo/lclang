"""Behavioral contracts for production source policies."""

import ast
from pathlib import Path

import pytest

from scripts.check_project import check_source, effective_source_lines


def failures(source: str) -> list[str]:
    """Check an in-memory declaration without creating files."""
    return check_source(source, Path("example.py"))


@pytest.mark.parametrize("count", [199, 200, 201])
def test_code_line_boundary_excludes_documentation_and_comments(count: int) -> None:
    """Only actual implementation lines consume the inclusive budget."""
    source = '"""Example module."""\nimport os\n# Explanation.\n\n' + "value = 1\n" * count
    assert effective_source_lines(source, ast.parse(source)) == count
    assert any("exceeds 200" in item for item in failures(source)) is (count > 200)


def test_multiline_code_imports_and_strings_preserve_physical_count() -> None:
    """Comments disappear without discarding executable text on the same line."""
    source = '''"""Module documentation.
    Not code.
    """
from pathlib import (
    Path,
)
import os; value = 1  # Actual code survives the import.
def calculate(
    value: int,
) -> str:
    """Return text.

    :param value: Input.
    :returns: Text.
    """
    # Local explanation.
    return """first
second
third"""
'''
    assert effective_source_lines(source, ast.parse(source)) == 7


def test_standalone_runtime_text_is_not_mistaken_for_a_docstring() -> None:
    """Only declaration and attribute documentation is excluded from the budget."""
    source = '"""Module."""\npass\n"""ordinary\ntext"""\n'
    assert effective_source_lines(source, ast.parse(source)) == 3


def test_exception_contract_respects_handler_and_nested_scope() -> None:
    """Handled exceptions and nested declarations do not leak into outer docs."""
    source = '''"""Exception example."""
def outer() -> int:
    """Return a recovered value.

    :returns: One.
    """
    def nested() -> None:
        """Fail deliberately.

        :raises ValueError: Always.
        """
        raise ValueError()
    try:
        raise KeyError()
    except LookupError:
        return 1
'''
    assert failures(source) == []
    assert any(
        ":raises ValueError:" in item
        for item in failures(
            '"""Module."""\ndef fail() -> None:\n    """Fail."""\n    raise ValueError()\n'
        )
    )


@pytest.mark.parametrize(
    "name, valid",
    [
        ("__repr__", True),
        ("__del__", True),
        ("__fspath__", True),
        ("__matmul__", True),
        ("_helper__", False),
        ("__class__", False),
    ],
)
def test_only_protocol_methods_receive_dunder_exemption(name: str, valid: bool) -> None:
    """An arbitrary trailing dunder does not bypass semantic naming."""
    source = f'''"""Module."""
class Value:
    """Example value."""
    def {name}(self) -> str:
        """Describe the value.

        :returns: Text.
        """
        return "value"
'''
    assert bool(failures(source)) is not valid


def test_protocol_spelling_does_not_exempt_a_top_level_function() -> None:
    """Only a real class method can implement the repr protocol."""
    assert any(
        "underscore" in item
        for item in failures(
            '"""Module."""\ndef __repr__() -> str:\n'
            '    """Render.\n\n    :returns: Text.\n    """\n    return "value"\n'
        )
    )


def test_named_constants_and_enum_groups_require_explanation() -> None:
    """Constant groups can share a preceding explanation."""
    assert failures('"""Module."""\nLIMIT = 200\n')
    assert failures(
        '"""Module."""\nfrom enum import Enum\n'
        'class Kind(Enum):\n    """Kind."""\n    First = "first"\n'
    )
    assert failures('''"""Module."""
# Measured in code lines; project policy uses 200 to keep modules reviewable.
LIMIT = 200
''') == []
    assert failures('''"""Module."""
from enum import Enum
# Unitless protocol labels; both outcomes are explicit for deterministic routing.
class Outcome(Enum):
    """Protocol outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
''') == []
