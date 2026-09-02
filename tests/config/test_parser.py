"""Behavioural tests for `.lclcfg` document parsing."""

import io
import logging
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
from lclang.diagnostics import internal_verbose_scope
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


def test_using_accepts_only_literal_and_semantic_fstring_targets() -> None:
    """Dynamic using syntax retains its parsed source-aware f-string AST."""
    document = parse_config('using f"parts/{name}.lclcfg"\n')
    using = document.declarations[0]
    assert isinstance(using, ConfigUsing)
    assert isinstance(using.target, LclJoinedString)

    for text in (
        "using name\n",
        "using 1\n",
        'using "parts/" + name + ".lclcfg"\n',
    ):
        with pytest.raises(LclConfigSyntaxError, match="string"):
            parse_config(text)


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


def test_parse_qualified_definition_and_proxy_marker() -> None:
    """Config left-hand paths and the standalone marker use core syntax."""
    import lclang

    document = parse_config("A: FRAME_PROXY\nA.B.x: 42\n")
    first, second = document.declarations
    assert isinstance(first, ConfigDefinition)
    assert isinstance(second, ConfigDefinition)
    assert str(first.name) == "A"
    assert isinstance(first.expression, LclConstant)
    assert first.expression.value is lclang.FRAME_PROXY
    assert str(second.name) == "A.B.x"


def test_masked_definition_marker_normalizes_exact_qualified_names() -> None:
    """A trailing bang records policy without becoming part of lookup syntax."""
    document = parse_config("token!: 'secret'\nservice.password!: token\nplain: token\n")
    first, second, third = document.declarations
    assert isinstance(first, ConfigDefinition)
    assert isinstance(second, ConfigDefinition)
    assert isinstance(third, ConfigDefinition)
    assert (str(first.name), first.masked) == ("token", True)
    assert (str(second.name), second.masked) == ("service.password", True)
    assert (str(third.name), third.masked) == ("plain", False)


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
        "value!!: 1\n",
        "value !: 1\n",
        "!: 1\n",
        "for: 1\n",
        "empty: # nothing\n",
    ):
        with pytest.raises((LclConfigSyntaxError, LclConfigVersionError)):
            parse_config(text)


def test_config_expression_tracing_covers_success_and_both_error_families() -> None:
    """Verbose parsing retains canonical success and structured syntax failures."""
    output = io.StringIO()
    logger = logging.Logger("config-trace", logging.DEBUG)
    logger.addHandler(logging.StreamHandler(output))
    with internal_verbose_scope(logger):
        document = parse_config("value: 1 + 2\n")
        assert document.declarations[0].ordinal == 0
        with pytest.raises(LclConfigSyntaxError):
            parse_config("value: 1 +\n")
        with pytest.raises(LclConfigSyntaxError):
            parse_config("value: __file__\n")
    trace = output.getvalue()
    assert "ast=(LclBinary) 1 + 2" in trace
    assert trace.count("[lclang.parse]") == 3
