"""Immutable values shared by the typed CLI framework."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from pathlib import Path
from typing import Self

from lclang.cli.validation import freeze_mapping, normalize_text, require_lcl_identifier

# Default percent-style format retaining diagnostic and call-argument fields.
DEFAULT_LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s %(message)s args=%(args)r"
)
# Required percent fields that custom formats must retain.
REQUIRED_LOG_FIELDS = ("asctime", "filename", "lineno", "funcName", "message", "args")


@dataclass(frozen=True, slots=True)
class ParameterDoc:
    """Describe one Frame-resolved command parameter for help and presence checks.

    :param name: Valid LCL binding name.
    :param value_type: Display-only type annotation.
    :param required: Whether execution requires a binding to exist.
    :param description: Human-readable help text.
    :param default: Literal default, where ``None`` means no default.
    """

    name: str
    value_type: object
    required: bool
    description: str
    default: object = None

    def __post_init__(self) -> None:
        """Validate and normalize declaration metadata.

        :returns: ``None``.
        :raises TypeError: If required is not Boolean or description is not text.
        :raises ValueError: If name is not an LCL identifier.
        """
        object.__setattr__(self, "name", require_lcl_identifier(self.name, "parameter name"))
        if not isinstance(self.required, bool):
            raise TypeError("parameter required must be Boolean")
        object.__setattr__(self, "description", normalize_text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class CliParams:
    """Snapshot one parsed command-line invocation.

    :param executable_path: Exact Python executable token.
    :param command: Routed nested command segments.
    :param as_of_date: Effective invocation date.
    :param dryrun: Handler-visible dryrun signal.
    :param config_file_path: Optional raw configuration path.
    :param overrides: Raw right-biased strings or valueless ``True`` overrides.
    """

    executable_path: str
    command: Sequence[str]
    as_of_date: date
    dryrun: bool
    config_file_path: str | None
    overrides: Mapping[str, str | bool]

    def __post_init__(self) -> None:
        """Detach containers and validate scalar fields.

        :returns: ``None``.
        :raises TypeError: If a scalar or override has an invalid type.
        :raises ValueError: If executable, command, or config text is empty.
        """
        if not isinstance(self.executable_path, str):
            raise TypeError("executable path must be text")
        if not self.executable_path:
            raise ValueError("executable path cannot be empty")
        command = tuple(self.command)
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise ValueError("command path must contain non-empty text segments")
        if not isinstance(self.as_of_date, date):
            raise TypeError("as-of date must be a date")
        if not isinstance(self.dryrun, bool):
            raise TypeError("dryrun must be Boolean")
        if self.config_file_path is not None and not isinstance(self.config_file_path, str):
            raise TypeError("config path must be text or None")
        if self.config_file_path == "":
            raise ValueError("config path cannot be empty")
        overrides = freeze_mapping(self.overrides, "overrides")
        if any(not isinstance(value, str) and value is not True for value in overrides.values()):
            raise TypeError("override values must be strings or True")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "overrides", overrides)


class CliResultStatus(IntEnum):
    """Map handler outcomes directly to process-compatible integer statuses."""

    SUCCESS = 0
    FAILURE = 1
    EXCEPTION = 2


@dataclass(frozen=True, slots=True)
class CliResult:
    """Describe one command outcome.

    :param result_status: Status mapped to the integer return code.
    :param description: Unicode text printed and logged when non-empty.
    """

    result_status: CliResultStatus
    description: str

    @classmethod
    def success(cls, msg: str) -> Self:
        """Create a successful result with one description.

        :param msg: Unicode result text, including empty text.
        :returns: Successful result of the selected class.
        :raises TypeError: If *msg* is not text.
        """
        return cls(CliResultStatus.SUCCESS, msg)

    @classmethod
    def fail(cls, msg: str) -> Self:
        """Create a failed result with one description.

        :param msg: Unicode result text, including empty text.
        :returns: Failed result of the selected class.
        :raises TypeError: If *msg* is not text.
        """
        return cls(CliResultStatus.FAILURE, msg)

    def __post_init__(self) -> None:
        """Reject incompatible status and description values.

        :returns: ``None``.
        :raises TypeError: If either field has the wrong public type.
        """
        if not isinstance(self.result_status, CliResultStatus):
            raise TypeError("result status must be CliResultStatus")
        if not isinstance(self.description, str):
            raise TypeError("result description must be text")


@dataclass(frozen=True, slots=True)
class LogConfig:
    """Define effective file logging defaults.

    :param log_dir: Directory for the log file, or ``None`` to disable output.
    :param log_file_name: Leaf log filename.
    :param log_level: Standard integer level or case-insensitive level name.
    :param log_format: Percent-style logging format with required fields.
    """

    log_dir: str | None = None
    log_file_name: str = "lclang.log"
    log_level: str | int = "INFO"
    log_format: str = DEFAULT_LOG_FORMAT

    def __post_init__(self) -> None:
        """Validate logging values without touching the filesystem.

        :returns: ``None``.
        :raises TypeError: If a field has an unsupported type.
        :raises ValueError: If a path, level, or format is invalid.
        """
        if self.log_dir is not None and not isinstance(self.log_dir, str):
            raise TypeError("log directory must be text or None")
        if self.log_dir == "":
            raise ValueError("log directory cannot be empty")
        if not isinstance(self.log_file_name, str):
            raise TypeError("log filename must be text")
        if not self.log_file_name or Path(self.log_file_name).name != self.log_file_name:
            raise ValueError("log filename must be a non-empty leaf name")
        if isinstance(self.log_level, str):
            if self.log_level.upper() not in logging.getLevelNamesMapping():
                raise ValueError("unknown log level")
        elif not isinstance(self.log_level, int):
            raise TypeError("log level must be text or integer")
        if not isinstance(self.log_format, str):
            raise TypeError("log format must be text")
        if any(f"%({name})" not in self.log_format for name in REQUIRED_LOG_FIELDS):
            raise ValueError("log format must contain every required diagnostic field")


@dataclass(frozen=True, slots=True)
class CliConfig:
    """Hold framework-wide command execution defaults.

    :param log_config: Immutable default logger configuration.
    """

    log_config: LogConfig = field(default_factory=LogConfig)

    def __post_init__(self) -> None:
        """Require the public logging configuration type.

        :returns: ``None``.
        :raises TypeError: If *log_config* is not a :class:`LogConfig`.
        """
        if not isinstance(self.log_config, LogConfig):
            raise TypeError("CLI log configuration must be LogConfig")
