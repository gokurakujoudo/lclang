"""Resolve console and file declarations after template inheritance."""

from __future__ import annotations

import codecs
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from lclang.logger.rotation import RotationConfig, rotation_config
from lclang.logger.validation import boolean, fields, level, names, positive

# Unitless field names from the public logger schema; shared with the CLI adapter for validation.
CONSOLE_FIELDS = {"enabled", "level", "stream"}
FILE_FIELDS = {
    "enabled",
    "directory",
    "filename",
    "level",
    "encoding",
    "flush_interval",
    "logger_names",
    "rotation",
}


@dataclass(frozen=True, slots=True)
class ConsoleConfig:
    """Hold one borrowed output stream's settings.

    :param enabled: Whether to create console output.
    :param level: Minimum numeric logging severity.
    :param stream: stdout/stderr name or borrowed text stream.
    """

    enabled: bool
    level: int
    stream: object


@dataclass(frozen=True, slots=True)
class FileConfig:
    """Hold a fully resolved file policy.

    :param enabled: Whether the sink performs any I/O.
    :param directory: Output directory, absent only for disabled sinks.
    :param filename: Validated leaf filename template.
    :param level: Minimum numeric logging severity.
    :param encoding: Registered text encoding.
    :param flush_interval: Maximum buffered flush interval in seconds.
    :param logger_names: Exact or dotted-ancestor source names; empty accepts all.
    :param rotation: Independent size and time policy.
    """

    enabled: bool
    directory: Path | None
    filename: str
    level: int
    encoding: str
    flush_interval: float
    logger_names: tuple[str, ...]
    rotation: RotationConfig


def console_config(value: object) -> ConsoleConfig:
    """Validate a console declaration without writing to its stream.

    :param value: Console field mapping.
    :returns: Resolved console settings.
    :raises TypeError: If a stream is not text-writable.
    """
    path = "logger.console"
    data = fields(value, CONSOLE_FIELDS, path)
    stream = data.get("stream", "stderr")
    if stream not in ("stdout", "stderr") and not (
        callable(getattr(stream, "write", None)) and callable(getattr(stream, "flush", None))
    ):
        raise TypeError(f"{path}.stream: expected stdout, stderr, or a text stream")
    return ConsoleConfig(
        boolean(data.get("enabled", True), f"{path}.enabled"),
        level(data.get("level", "INFO"), f"{path}.level"),
        stream,
    )


def leaf_filename(value: object, path: str) -> str:
    """Check portable leaf names and supported template substitutions.

    :param value: Filename template.
    :param path: Diagnostic configuration path.
    :returns: Validated template.
    :raises ValueError: If the name or substitution is invalid.
    """
    if not isinstance(value, str) or not value or value in (".", ".."):
        raise ValueError(f"{path}: expected nonempty leaf filename")
    if any(char in value for char in '/\\\x00\n\r<>:"|?*') or value.endswith((" ", ".")):
        raise ValueError(f"{path}: expected portable leaf filename")
    try:
        parts = list(Formatter().parse(value))
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error
    for _, key, spec, conversion in parts:
        if key is not None and (key not in ("pid", "process") or spec or conversion):
            raise ValueError(f"{path}: only {{pid}} and {{process}} are supported")
    return value


def file_config(name: str, value: Mapping[str, object], *, template: bool = False) -> FileConfig:
    """Validate a merged sink or a partial default template.

    :param name: Sink name for diagnostics and generated filenames.
    :param value: Already merged file fields.
    :param template: Whether missing required output details remain acceptable.
    :returns: Resolved file settings.
    :raises TypeError: If directory or encoding has an invalid type.
    :raises ValueError: If an enabled sink lacks a directory.
    """
    path = f"logger.file.{name}"
    data = fields(value, FILE_FIELDS, path)
    enabled = boolean(data.get("enabled", True), f"{path}.enabled")
    directory = data.get("directory")
    if directory is not None and not isinstance(directory, (str, os.PathLike)):
        raise TypeError(f"{path}.directory: expected a path")
    if enabled and not template and not directory:
        raise ValueError(f"{path}.directory: enabled sink requires a directory")
    encoding = data.get("encoding", "utf-8")
    if not isinstance(encoding, str):
        raise TypeError(f"{path}.encoding: expected encoding name")
    try:
        codecs.lookup(encoding)
    except LookupError as error:
        raise ValueError(f"{path}.encoding: {error}") from error
    return FileConfig(
        enabled,
        None if directory is None else Path(directory),
        leaf_filename(data.get("filename", f"lclang.{name}.{{pid}}.log"), f"{path}.filename"),
        level(data.get("level", "INFO"), f"{path}.level"),
        encoding,
        positive(data.get("flush_interval", 1.0), f"{path}.flush_interval"),
        names(data.get("logger_names", ()), f"{path}.logger_names"),
        rotation_config(data.get("rotation", {}), f"{path}.rotation", partial=template),
    )
