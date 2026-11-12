"""Synchronous text file reading with deterministic cleanup.

Defines ``read_text_file``.
"""

from os import PathLike, fspath
from pathlib import Path

from lclang.error import LclStandardError, LclValidationError, StandardLibraryErrorCode
from lclang.error.native_wrap import wrap_failure
from lclang.error.operation_guard import guard_failure


@guard_failure(LclStandardError, StandardLibraryErrorCode.E81_TEXT_FILE_NATIVE_FAILURE)
def read_text_file(fp: str | PathLike[str], encoding: str = "utf-8") -> str:
    """Read a complete text file and close it before returning or raising.

    :param fp: Text path, relative to the process working directory if not absolute.
    :param encoding: Python text encoding name; UTF-8 by default.
    :returns: Complete decoded text with universal newlines and unchanged whitespace.
    :raises LclValidationError: If the path or encoding has an unsupported type.
    :raises LclStandardError: If opening, decoding, reading, or closing fails,
        retaining the original exception as its cause.

    .. note::
       Reading is synchronous and uncached. No encoding detection or BOM removal
       is performed beyond the selected codec's behavior.
    """
    if not isinstance(fp, (str, PathLike)):
        raise LclValidationError(
            "fp must be a text path", code=StandardLibraryErrorCode.E81_TEXT_FILE_PATH_TYPE
        )
    path = fspath(fp)
    if not isinstance(path, str):
        raise LclValidationError(
            "fp must resolve to a text path", code=StandardLibraryErrorCode.E81_TEXT_FILE_PATH_TYPE
        )
    if not isinstance(encoding, str):
        raise LclValidationError(
            "encoding must be a string", code=StandardLibraryErrorCode.E81_TEXT_FILE_ENCODING_TYPE
        )
    try:
        with Path(path).open("r", encoding=encoding, errors="strict") as stream:
            return stream.read()
    except FileNotFoundError as error:
        raise wrap_failure(
            error, LclStandardError, StandardLibraryErrorCode.E81_TEXT_FILE_NOT_FOUND
        ) from error
    except PermissionError as error:
        raise wrap_failure(
            error, LclStandardError, StandardLibraryErrorCode.E81_TEXT_FILE_PERMISSION
        ) from error
    except UnicodeError as error:
        raise wrap_failure(
            error, LclStandardError, StandardLibraryErrorCode.E81_TEXT_FILE_DECODING
        ) from error
    except LookupError as error:
        raise wrap_failure(
            error, LclStandardError, StandardLibraryErrorCode.E81_TEXT_FILE_UNKNOWN_ENCODING
        ) from error
