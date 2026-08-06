"""Unit tests mirroring :mod:`pylcl.lang.lexer.escapes`."""

import pytest

from pylcl.lang.lexer.escapes import EscapeDecodeError, decode_content


def test_decode_content_handles_text_raw_and_bytes_modes() -> None:
    """The decoder owns mode-specific results independently of quote parsing."""
    assert decode_content(r"a\n", raw=False, bytes_mode=False) == "a\n"
    assert decode_content(r"a\n", raw=True, bytes_mode=False) == r"a\n"
    assert decode_content(r"a\x42", raw=False, bytes_mode=True) == b"aB"
    assert decode_content(r"a\n", raw=True, bytes_mode=True) == b"a\\n"


def test_decode_error_preserves_relative_boundary() -> None:
    """Quote matching can translate decoder failures into absolute spans."""
    with pytest.raises(EscapeDecodeError) as caught:
        decode_content(r"\q", raw=False, bytes_mode=False)
    assert caught.value.message == r"unsupported escape \q"
    assert caught.value.end == 2
