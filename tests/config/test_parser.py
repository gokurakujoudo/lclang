"""Behavioural tests for `.lclcfg` document parsing."""

from pathlib import Path

import pytest

from lclang.ast import LclBinary, LclConstant, LclJoinedString, LclList
from lclang.config import (
    ConfigDefinition,
    ConfigUsing,
    LclConfigSyntaxError,
    LclConfigVersionError,
    parse_config,
)
from lclang.runtime import analyze_dependencies


def test_parse_colon_definitions_comments_continuation_and_duplicates(tmp_path: Path) -> None:
    """A practical document retains declarations, coordinates, and later duplicates."""
    path = tmp_path / "main.lclcfg"
    document = parse_config(
        "# heading\r\n"
        "__LCL_VERSION__: 1 # current\r\n"
        "base: 1\r\n"
        "total: (base + \\ # continued\r\n"
        "  2) # result\r\n"
        "base: 3\r\n"
        "using \"child.lclcfg\" # expand\r\n"
        "\r\n",
        source_name="main",
        source_path=path,
    )
    assert document.version == 1
    assert [type(item) for item in document.declarations] == [
        ConfigDefinition,
        ConfigDefinition,
        ConfigDefinition,
        ConfigUsing,
    ]
    definitions = [item for item in document.declarations if isinstance(item, ConfigDefinition)]
    assert [str(item.name) for item in definitions] == ["base", "total", "base"]
    assert isinstance(definitions[1].expression, LclBinary)
    assert definitions[1].span.start.line == 4
    using = document.declarations[-1]
    assert isinstance(using, ConfigUsing)
    assert using.target == "child.lclcfg"


def test_file_magic_becomes_eager_constants_with_physical_origin(tmp_path: Path) -> None:
    """Magic identifiers disappear from the runtime AST while retaining their spans."""
    path = (tmp_path / "magic.lclcfg").resolve()
    document = parse_config(
        "values: [__file__, __dir__, '__file__']\n",
        source_path=path,
    )
    definition = document.declarations[0]
    assert isinstance(definition, ConfigDefinition)
    assert isinstance(definition.expression, LclList)
    first, second, third = definition.expression.elements
    assert isinstance(first, LclConstant) and first.value == str(path)
    assert isinstance(second, LclConstant) and second.value == str(path.parent)
    assert isinstance(third, LclConstant) and third.value == "__file__"
    assert first.span.start.line == 1

    formatted = parse_config("value: f'{__file__}'\n", source_path=path).declarations[0]
    assert isinstance(formatted, ConfigDefinition)
    assert isinstance(formatted.expression, LclJoinedString)
    assert analyze_dependencies(formatted.expression) == ()


def test_nested_file_magic_requires_a_physical_origin() -> None:
    """Magic inside an f-string field cannot bypass the path requirement."""
    with pytest.raises(LclConfigSyntaxError, match="physical source path") as caught:
        parse_config("value: f'{__file__}'\n")
    assert caught.value.span is not None
    assert caught.value.span.origin.path is None


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("value = 1\n", LclConfigSyntaxError),
        ("value: [1,\n2]\n", LclConfigSyntaxError),
        ("value: 1 \\\n# broken\n", LclConfigSyntaxError),
        ("value: __file__\n", LclConfigSyntaxError),
        ("value: 1\n__LCL_VERSION__: 1\n", LclConfigVersionError),
        ("__LCL_VERSION__: 2\nvalue: 1\n", LclConfigVersionError),
        ("__private: 1\n", LclConfigSyntaxError),
        ("using f'child.lclcfg'\n", LclConfigSyntaxError),
        ("using 'child.txt'\n", LclConfigSyntaxError),
    ],
)
def test_invalid_documents_are_structured(text: str, error: type[Exception]) -> None:
    """Malformed declarations fail without accidental fallback behavior."""
    with pytest.raises(error):
        parse_config(text)


def test_parser_public_validation_and_declaration_rainy_branches(tmp_path: Path) -> None:
    """Public input types and declaration-specific malformed forms are rejected."""
    with pytest.raises(TypeError):
        parse_config(b"value: 1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_config("", source_name=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_config("", source_name="")
    with pytest.raises(TypeError):
        parse_config("", source_path=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        parse_config("", source_path=tmp_path / "bad.txt")
    for text in (
        "__LCL_VERSION__ 1\n",
        "__LCL_VERSION__: name\n",
        "__LCL_VERSION__: 'unterminated\n",
        "__LCL_VERSION__: 1 \\\nvalue: 1\n",
        "using 'child.lclcfg' \\\nvalue: 1\n",
        "using @\n",
        "using 'unterminated\n",
        "using ''\n",
        "bad-name: 1\n",
        "bad$: 1\n",
        "for: 1\n",
        "empty: # nothing\n",
    ):
        with pytest.raises((LclConfigSyntaxError, LclConfigVersionError)):
            parse_config(text)
