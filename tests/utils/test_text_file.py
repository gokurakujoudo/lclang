"""Behavioral tests for complete text reads and file ownership."""

from io import StringIO, TextIOWrapper
from os import PathLike
from os.path import relpath
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import pytest

from lclang.error import LclStandardError, LclValidationError
from lclang.utils import read_text_file


@pytest.mark.parametrize("content", ["", "  中文\nlast ", "\ufeffhello", "a\r\nb\rc\n"])
def test_text_contents_and_closure(content: str) -> None:
    """Text decoding preserves whitespace and normalizes universal newlines."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "text.txt"
        path.write_bytes(content.encode("utf-8"))
        expected = content.replace("\r\n", "\n").replace("\r", "\n")
        assert read_text_file(path) == expected
        assert read_text_file(str(path)) == expected
        path.unlink()


def test_explicit_encoding_and_relative_path() -> None:
    """Both encoding argument forms work, and relative paths use the cwd."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "text.txt"
        path.write_bytes("中文".encode("gbk"))
        assert read_text_file(path, "gbk") == "中文"
        assert read_text_file(path, encoding="gbk") == "中文"
        assert read_text_file(relpath(path), "gbk") == "中文"


@pytest.mark.parametrize("value", [None, 3, b"text.txt", StringIO("text")])
def test_invalid_path_types(value: object) -> None:
    """Descriptors, binary paths and streams are rejected before opening."""
    with pytest.raises(LclValidationError) as caught:
        read_text_file(cast(str, value))
    assert caught.value.code == "LCL981191"


def test_binary_pathlike_and_encoding_type() -> None:
    """PathLike must return text; an omitted encoding differs from None."""

    class BinaryPath(PathLike[bytes]):
        def __fspath__(self) -> bytes:
            return b"text.txt"

    with pytest.raises(LclValidationError) as caught:
        read_text_file(cast(str, BinaryPath()))
    assert caught.value.code == "LCL981191"
    with pytest.raises(LclValidationError) as caught:
        read_text_file("text.txt", cast(str, None))
    assert caught.value.code == "LCL981111"


@pytest.mark.parametrize(
    ("encoding", "data", "cause", "code"),
    [
        ("utf-8", b"\xff", UnicodeDecodeError, "LCL981731"),
        ("no-such-text-codec", b"text", LookupError, "LCL981251"),
    ],
)
def test_codec_failures(encoding: str, data: bytes, cause: type[Exception], code: str) -> None:
    """Codec failures retain native causes and leave no owned open file."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "text.txt"
        path.write_bytes(data)
        with pytest.raises(LclStandardError) as caught:
            read_text_file(path, encoding)
        assert caught.value.code == code
        assert isinstance(caught.value.__cause__, cause)
        path.unlink()


def test_missing_file() -> None:
    """Missing files fail without creating a replacement."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "missing.txt"
        with pytest.raises(LclStandardError) as caught:
            read_text_file(path)
        assert caught.value.code == "LCL981711"
        assert isinstance(caught.value.__cause__, FileNotFoundError)
        assert not path.exists()


@pytest.mark.parametrize("error", [PermissionError("denied"), OSError("read failed")])
def test_io_failures(error: OSError) -> None:
    """Permission and other I/O failures keep the exact native exception."""
    with (
        patch.object(Path, "open", side_effect=error),
        pytest.raises(LclStandardError) as caught,
    ):
        read_text_file("text.txt")
    assert caught.value.__cause__ is error
    assert caught.value.code == ("LCL981721" if isinstance(error, PermissionError) else "LCL981890")


@pytest.mark.parametrize("data", [b"hello", b"\xff"])
def test_stream_is_closed_after_read(data: bytes) -> None:
    """The owned real text stream closes after success and decode failure."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "text.txt"
        path.write_bytes(data)
        stream: TextIOWrapper = path.open(encoding="utf-8")
        with patch.object(Path, "open", return_value=stream):
            if data == b"hello":
                assert read_text_file(path) == "hello"
            else:
                with pytest.raises(LclStandardError):
                    read_text_file(path)
        assert stream.closed
