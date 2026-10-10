"""Immutable values shared by the typed CLI framework.

Defines ``ParameterDoc``, ``CliParams``, ``CliResultStatus``, ``CliResult``, ``CliConfig``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Self

from lclang.cli.declaration_validation import (
    freeze_mapping,
    normalize_text,
    require_lcl_qualified_name,
)
from lclang.common.binding_mask import normalize_masked_mapping, split_masked_name
from lclang.error import CliErrorCode, LclCliError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.logger import LoggerHandlerConfig


@guard_constructor(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
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

    @guard_failure(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate and normalize declaration metadata.

        :returns: ``None``.
        :raises LclValidationError: If required is not Boolean or description is not text.
        :raises LclValidationError: If name is not an LCL qualified name.
        """
        name, marked = split_masked_name(self.name)
        object.__setattr__(self, "name", require_lcl_qualified_name(name, "parameter name"))
        if not isinstance(self.required, bool):
            raise LclValidationError(
                "parameter required must be Boolean",
                code=CliErrorCode.E14_PARAMETER_REQUIRED_MUST_BE_BOOLEAN,
            )
        if not isinstance(self.masked, bool):
            raise LclValidationError(
                "parameter masked must be Boolean",
                code=CliErrorCode.E14_PARAMETER_REQUIRED_MUST_BE_BOOLEAN,
            )
        object.__setattr__(self, "masked", self.masked or marked)
        object.__setattr__(self, "description", normalize_text(self.description, "description"))


@guard_constructor(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
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
    masked_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)
    script_path: str = field(default="script.py", kw_only=True)
    raw_argv: Sequence[str] | None = field(default=None, kw_only=True)

    @guard_failure(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Detach containers and validate scalar fields.

        :returns: ``None``.
        :raises LclValidationError: If a scalar or override has an invalid type.
        :raises LclValidationError: If executable, command, or config text is empty.
        """
        if not isinstance(self.executable_path, str):
            raise LclValidationError(
                "executable path must be text", code=CliErrorCode.E14_EXECUTABLE_PATH_MUST_BE_TEXT
            )
        if not self.executable_path:
            raise LclValidationError(
                "executable path cannot be empty",
                code=CliErrorCode.E14_EXECUTABLE_PATH_CANNOT_BE_EMPTY,
            )
        if not isinstance(self.script_path, str):
            raise LclValidationError(
                "script path must be text", code=CliErrorCode.E14_EXECUTABLE_PATH_MUST_BE_TEXT
            )
        if not self.script_path:
            raise LclValidationError(
                "script path cannot be empty", code=CliErrorCode.E14_EXECUTABLE_PATH_CANNOT_BE_EMPTY
            )
        raw_argv = None if self.raw_argv is None else tuple(self.raw_argv)
        if raw_argv is not None and any(not isinstance(item, str) or not item for item in raw_argv):
            raise LclValidationError(
                "raw argv tokens must be non-empty text",
                code=CliErrorCode.E14_RAW_ARGV_TOKENS_MUST_BE_NON_EMPTY_TEXT,
            )
        command = tuple(self.command)
        if not command or any(not isinstance(item, str) or not item for item in command):
            raise LclValidationError(
                "command path must contain non-empty text segments",
                code=CliErrorCode.E14_COMMAND_PATH_MUST_CONTAIN_NON_EMPTY_TEXT_SEGMENTS,
            )
        if not isinstance(self.as_of_date, date):
            raise LclValidationError(
                "as-of date must be a date", code=CliErrorCode.E14_AS_OF_DATE_MUST_BE_A_DATE
            )
        if not isinstance(self.dryrun, bool):
            raise LclValidationError(
                "dryrun must be Boolean", code=CliErrorCode.E14_PARAMETER_REQUIRED_MUST_BE_BOOLEAN
            )
        if not isinstance(self.verbose, bool):
            raise LclValidationError(
                "verbose must be Boolean", code=CliErrorCode.E14_PARAMETER_REQUIRED_MUST_BE_BOOLEAN
            )
        if self.config_file_path is not None and not isinstance(self.config_file_path, str):
            raise LclValidationError(
                "config path must be text or None",
                code=CliErrorCode.E14_EXECUTABLE_PATH_MUST_BE_TEXT,
            )
        if self.config_file_path == "":
            raise LclValidationError(
                "config path cannot be empty", code=CliErrorCode.E14_EXECUTABLE_PATH_CANNOT_BE_EMPTY
            )
        overrides = freeze_mapping(self.overrides, "overrides")
        normalized, masked_names = normalize_masked_mapping(overrides, self.masked_names)
        if any(not isinstance(value, str) and value is not True for value in normalized.values()):
            raise LclValidationError(
                "override values must be strings or True",
                code=CliErrorCode.E14_EXECUTABLE_PATH_MUST_BE_TEXT,
            )
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "overrides", freeze_mapping(normalized, "overrides"))
        object.__setattr__(self, "masked_names", masked_names)
        object.__setattr__(self, "raw_argv", raw_argv)


class CliResultStatus(IntEnum):
    """Map handler outcomes directly to process-compatible integer statuses."""

    # Unitless result codes are the public CLI status contract; distinct values distinguish
    # successful, failed, exceptional and covered execution.
    SUCCESS = 0
    FAILURE = 1
    EXCEPTION = 2
    FAILURE_COVERED = 3


@guard_constructor(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class CliResult:
    """Describe one command outcome.

    :param result_status: Status mapped to the integer return code.
    :param description: Unicode text printed and logged when non-empty.
    """

    result_status: CliResultStatus
    description: str

    @classmethod
    @guard_failure(LclCliError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
    def success(cls, msg: str) -> Self:
        """Create a successful result with one description.

        :param msg: Unicode result text, including empty text.
        :returns: Successful result of the selected class.
        :raises LclValidationError: If *msg* is not text.
        """
        return cls(CliResultStatus.SUCCESS, msg)

    @classmethod
    @guard_failure(LclCliError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
    def fail(cls, msg: str) -> Self:
        """Create a failed result with one description.

        :param msg: Unicode result text, including empty text.
        :returns: Failed result of the selected class.
        :raises LclValidationError: If *msg* is not text.
        """
        return cls(CliResultStatus.FAILURE, msg)

    @guard_failure(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Reject incompatible status and description values.

        :returns: ``None``.
        :raises LclValidationError: If either field has the wrong public type.
        """
        if not isinstance(self.result_status, CliResultStatus):
            raise LclValidationError(
                "result status must be CliResultStatus",
                code=CliErrorCode.E14_RESULT_STATUS_MUST_BE_CLIRESULTSTATUS,
            )
        if not isinstance(self.description, str):
            raise LclValidationError(
                "result description must be text",
                code=CliErrorCode.E14_EXECUTABLE_PATH_MUST_BE_TEXT,
            )


@guard_constructor(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class CliConfig:
    """Hold framework-wide command execution defaults.

    :param log_config: Immutable default logger configuration.
    """

    log_config: LoggerHandlerConfig = field(default_factory=LoggerHandlerConfig)

    @guard_failure(LclValidationError, CliErrorCode.E14_CLI_MODEL_CONSTRUCTION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Require the public logging configuration type.

        :returns: ``None``.
        :raises LclValidationError: If *log_config* is not a :class:`LoggerHandlerConfig`.
        """
        if not isinstance(self.log_config, LoggerHandlerConfig):
            raise LclValidationError(
                "CLI log configuration must be LoggerHandlerConfig",
                code=CliErrorCode.E14_CLI_LOG_CONFIGURATION_MUST_BE_LOGGERHANDLERCONFIG,
            )
