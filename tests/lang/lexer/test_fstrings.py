"""Unit tests mirroring :mod:`pylcl.lang.lexer.fstrings`."""

import pytest

from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind, scan_tokens
from pylcl.lang.lexer.fstring_values import FStringField, FStringText, FStringValue


def fvalue(source: str) -> FStringValue:
    """Return the lexical value of one f-string token."""
    token = scan_tokens(source)[0]
    assert token.kind is TokenKind.FSTRING
    assert isinstance(token.value, FStringValue)
    return token.value


def test_scans_text_expression_and_escaped_braces() -> None:
    """Literal text is decoded while replacement source is preserved."""
    assert fvalue(r"f'hello\n {{user}} {name}!'") == FStringValue(
        parts=(
            FStringText("hello\n {user} "),
            FStringField("name"),
            FStringText("!"),
        ),
        raw=False,
    )


def test_scans_debug_conversion_and_nested_format_field() -> None:
    """Field modifiers and recursive format specs retain their structure."""
    value = fvalue("f'{value=!r:>{width}}'")
    assert value == FStringValue(
        parts=(
            FStringField(
                expression="value",
                debug=True,
                conversion="r",
                format_spec=FStringValue(
                    parts=(FStringText(">"), FStringField("width")),
                    raw=False,
                ),
            ),
        ),
        raw=False,
    )


def test_nested_expression_delimiters_do_not_close_field() -> None:
    """Balanced call, mapping, and list delimiters stay inside expression text."""
    value = fvalue("f\"{call({'x': [1]})}\"")
    assert value.parts == (FStringField("call({'x': [1]})"),)


def test_comparison_equals_are_expression_source_not_modifiers() -> None:
    """Equality operators cannot be mistaken for conversion or debug syntax."""
    assert fvalue("f'{a == b}'").parts == (FStringField("a == b"),)
    assert fvalue("f'{a != b}'").parts == (FStringField("a != b"),)


def test_debug_field_allows_space_before_conversion() -> None:
    """Whitespace following debug equals is outside preserved expression source."""
    assert fvalue("f'{value = !s}'").parts == (
        FStringField("value", conversion="s", debug=True),
    )


def test_raw_and_triple_quoted_fstrings_preserve_mode() -> None:
    """Raw content keeps slashes and triple strings retain newlines."""
    assert fvalue(r"rf'{path}\n'") == FStringValue(
        parts=(FStringField("path"), FStringText(r"\n")),
        raw=True,
    )
    assert fvalue("f'''first\n{second}'''").parts == (
        FStringText("first\n"),
        FStringField("second"),
    )


@pytest.mark.parametrize(
    "source",
    [
        "f'{}'",
        "f'}'",
        "f'{value'",
        "f'{value!x}'",
        "f'{a\\b}'",
        "f'{a # comment}'",
        "f'a\nb'",
        "f'a\\",
        "f'{value:abc'",
        "f'{(value]}'",
        r"f'\q{value}'",
        "f\"{'unterminated}\"",
    ],
)
def test_invalid_fstring_is_source_aware(source: str) -> None:
    """Malformed interpolation reports through the public syntax hierarchy."""
    with pytest.raises(LclSyntaxError) as caught:
        scan_tokens(source)
    assert caught.value.span is not None
    assert caught.value.span.start.offset == 0
