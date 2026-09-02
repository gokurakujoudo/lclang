"""Immutable values shared by the typed CLI framework."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Self

from lclang.cli.validation import freeze_mapping, normalize_text, require_lcl_qualified_name
from lclang.masking import normalize_masked_mapping, split_masked_name
from lclang.utils.logging import LogConfig


@dataclass(frozen=True, slots=True)
class ParameterDoc:
    """Describe one Frame-resolved command parameter for help and presence checks.

    :param name: Valid LCL binding name.
    :param value_type: Display-only type annotation.
    :param required: Whether execution requires a binding to exist.
    :param description: Human-readable help text.
    :param default: Literal default, where ``None`` means no default.
    :param masked: Whether lclang-owned presentation hides this parameter.
    """

    name: str
    value_type: object
    required: bool
    description: str
    default: object = None
    masked: bool = False

    def __post_init__(self) -> None:
        """Validate and normalize declaration metadata.

        :returns: ``None``.
        :raises TypeError: If required is not Boolean or description is not text.
        :raises ValueError: If name is not an LCL qualified name.
        """
        name, marked = split_masked_name(self.name)
        object.__setattr__(self, "name", require_lcl_qualified_name(name, "parameter name"))
        if not isinstance(self.required, bool):
            raise TypeError("parameter required must be Boolean")
        if not isinstance(self.masked, bool):
            raise TypeError("parameter masked must be Boolean")
        object.__setattr__(self, "masked", self.masked or marked)
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
    :param verbose: Whether internal diagnostics are enabled for this invocation.
    :param masked_names: Immutable normalized override names to redact.
    :param script_path: Exact Python script token, or the direct-command fallback.
    :param raw_argv: Optional exact full invocation tokens before parsing.
    """

    executable_path: str
    command: Sequence[str]
    as_of_date: date
    dryrun: bool
    config_file_path: str | None
    overrides: Mapping[str, str | bool]
    verbose: bool = False
    masked_names: frozenset[str] = field(default_factory=frozenset, kw_only=True)
    script_path: str = field(default="script.py", kw_only=True)
    raw_argv: Sequence[str] | None = field(default=None, kw_only=True)

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
        if not isinstance(self.script_path, str):
            raise TypeError("script path must be text")
        if not self.script_path:
            raise ValueError("script path cannot be empty")
        raw_argv = None if self.raw_argv is None else tuple(self.raw_argv)
        if raw_argv is not None and any(
            not isinstance(item, str) or not item for item in raw_argv
        ):
            raise ValueError("raw argv tokens must be non-empty text")
        command = tuple(self.command)
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise ValueError("command path must contain non-empty text segments")
        if not isinstance(self.as_of_date, date):
            raise TypeError("as-of date must be a date")
        if not isinstance(self.dryrun, bool):
            raise TypeError("dryrun must be Boolean")
        if not isinstance(self.verbose, bool):
            raise TypeError("verbose must be Boolean")
        if self.config_file_path is not None and not isinstance(self.config_file_path, str):
            raise TypeError("config path must be text or None")
        if self.config_file_path == "":
            raise ValueError("config path cannot be empty")
        overrides = freeze_mapping(self.overrides, "overrides")
        normalized, masked_names = normalize_masked_mapping(overrides, self.masked_names)
        if any(not isinstance(value, str) and value is not True for value in normalized.values()):
            raise TypeError("override values must be strings or True")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "overrides", freeze_mapping(normalized, "overrides"))
        object.__setattr__(self, "masked_names", masked_names)
        object.__setattr__(self, "raw_argv", raw_argv)


class CliResultStatus(IntEnum):
    """Map handler outcomes directly to process-compatible integer statuses."""

    SUCCESS = 0
    FAILURE = 1
    EXCEPTION = 2
    FAILURE_COVERED = 3


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
