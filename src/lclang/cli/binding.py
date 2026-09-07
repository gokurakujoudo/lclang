"""Layered CLI Frame construction and reverse-order ownership."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime

from lclang.api import LCL_RUNTIME
from lclang.ast import LclAstNode, LclConstant
from lclang.cli.commands import Command
from lclang.cli.models import CliConfig, CliParams
from lclang.cli.overrides import partition_overrides, require_forced_result
from lclang.cli.runtime_keys import (
    RUNTIME_AS_OF_DATE_KEY,
    RUNTIME_CLI_PARAMS_KEY,
    RUNTIME_COMMAND_KEY,
    RUNTIME_DRYRUN_KEY,
    RUNTIME_EXECUTION_TIMESTAMP_KEY,
    RUNTIME_VERBOSE_KEY,
    RUNTIME_YMD_KEY,
)
from lclang.config import load_config
from lclang.errors import LclCliUsageError
from lclang.runtime import Frame, Module
from lclang.types import ModuleName

# Module label for the call-specific preset/import layer.
# Unitless layer identifiers below follow the CLI precedence contract and keep diagnostics
# distinguishable. Date formats use strftime directives: YYYYMMDD has day precision;
# YYYYMMDDhhmmss has local second precision. Compact numeric formats are stable configuration
# inputs and filename components.
IMPORTS_MODULE_NAME = ModuleName("LCL_IMPORTS")
# Module label for command and logger defaults.
DEFAULTS_MODULE_NAME = ModuleName("command_defaults")
# Module label used when no configuration file is selected.
EMPTY_CONFIG_MODULE_NAME = ModuleName("empty_config")
# Module label for raw CLI overrides.
OVERRIDES_MODULE_NAME = ModuleName("cli_overrides")
# Module label for the handler-visible runtime layer.
RUNTIME_MODULE_NAME = ModuleName("cli_runtime")
# Compact as-of date format exposed to CLI configuration.
YMD_FORMAT = "%Y%m%d"
# Compact local execution timestamp format exposed to CLI configuration.
EXECUTION_TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"


@dataclass(slots=True)
class FrameStack:
    """Own invocation-created Frames in parent-to-child order.

    :param frames: Frames to close in reverse order.
    :param closed: Whether close has completed or begun.
    """

    frames: tuple[Frame, ...]
    closed: bool = False

    async def close(self) -> None:
        """Close every owned Frame once in reverse order.

        :returns: ``None``.
        :raises Exception: If one or more Frame closes fail.
        """
        if self.closed:
            return
        self.closed = True
        failure: Exception | None = None
        for frame in reversed(self.frames):
            try:
                await asyncio.shield(frame.close())
            except Exception as error:
                if failure is None:
                    failure = error
        if failure is not None:
            raise failure


@dataclass(frozen=True, slots=True)
class CliBinding:
    """Pair the top handler Frame with its owned hierarchy.

    :param frame: Handler-visible top runtime Frame.
    :param stack: Owner for every invocation-created Frame.
    :param execution_config_names: Command and file names rendered by the audit.
    """

    frame: Frame
    stack: FrameStack
    execution_config_names: tuple[str, ...]


def default_definitions(command: Command, cli_config: CliConfig) -> dict[str, LclAstNode]:
    """Build constant command and logger default definitions.

    :param command: Selected command declaration.
    :param cli_config: Framework defaults.
    :returns: Fresh definition mapping.
    """
    log_config = cli_config.log_config
    definitions: dict[str, LclAstNode] = {
        "logger.log_dir": LclConstant(value=log_config.log_dir),
        "logger.log_file_name": LclConstant(value=log_config.log_file_name),
        "logger.log_level": LclConstant(value=log_config.log_level),
        "logger.log_format": LclConstant(value=log_config.log_format),
    }
    definitions.update(
        {
            parameter.name: LclConstant(value=parameter.default)
            for parameter in command.parameter_docs
            if parameter.default is not None
        }
    )
    return definitions


async def build_binding(command: Command, params: CliParams, cli_config: CliConfig) -> CliBinding:
    """Construct and validate one complete invocation Frame hierarchy.

    :param command: Selected command declaration.
    :param params: Parsed immutable invocation parameters.
    :param cli_config: Framework defaults.
    :returns: Owned binding with top runtime Frame.
    :raises LclCliUsageError: If a required parameter has no effective binding.
    :raises Exception: If config loading, construction, or required checks fail.
    """
    frames: list[Frame] = []
    stack = FrameStack(())
    execution_values: dict[str, object] = {
        RUNTIME_AS_OF_DATE_KEY: params.as_of_date,
        RUNTIME_CLI_PARAMS_KEY: params,
        RUNTIME_DRYRUN_KEY: params.dryrun,
        RUNTIME_VERBOSE_KEY: params.verbose,
        RUNTIME_YMD_KEY: params.as_of_date.strftime(YMD_FORMAT),
        RUNTIME_EXECUTION_TIMESTAMP_KEY: datetime.now(UTC)
        .astimezone()
        .strftime(EXECUTION_TIMESTAMP_FORMAT),
        RUNTIME_COMMAND_KEY: command.name,
    }
    try:
        preliminary_definitions, preliminary_values = partition_overrides(params)
        using_overrides = {**preliminary_values, **preliminary_definitions}
        imports = LCL_RUNTIME.derive(
            Module(IMPORTS_MODULE_NAME, {}),
            dict(command.preset),
            masked_names=command.masked_names,
        )
        frames.append(imports)
        defaults_module = Module(
            DEFAULTS_MODULE_NAME,
            default_definitions(command, cli_config),
            masked_names=frozenset(
                item.name
                for item in command.parameter_docs
                if item.masked and item.default is not None
            ),
        )
        defaults = imports.derive(defaults_module)
        frames.append(defaults)
        if params.config_file_path is None:
            config_module = Module(EMPTY_CONFIG_MODULE_NAME, {})
        else:
            config_module = (
                await load_config(
                    params.config_file_path,
                    overrides=using_overrides,
                )
            ).to_module()
        config = defaults.derive(config_module, execution_values)
        frames.append(config)
        strict_result = command.name in {"parse_lcl", "eval_lcl"} and (
            params.overrides.get("FORCE") is True
        )
        if strict_result:
            require_forced_result(params, preliminary_definitions, config)
        override_definitions = preliminary_definitions
        override_values = preliminary_values
        runtime_values: dict[str, object] = {
            **override_values,
            **execution_values,
        }
        overrides = config.derive(
            Module(
                OVERRIDES_MODULE_NAME,
                override_definitions,
                masked_names=params.masked_names & override_definitions.keys(),
            ),
            runtime_values,
            masked_names=params.masked_names,
        )
        frames.append(overrides)
        runtime = overrides.derive(
            Module(RUNTIME_MODULE_NAME, {}),
            masked_names=frozenset(
                item.name for item in command.parameter_docs if item.masked
            ),
        )
        frames.append(runtime)
        stack = FrameStack(tuple(frames))
        missing = [
            item.name
            for item in command.parameter_docs
            if item.required and not runtime.has(item.name)
        ]
        if missing:
            raise LclCliUsageError("missing required parameter: " + ", ".join(missing))
        audit_names = {
            *(item.name for item in command.parameter_docs),
            *config_module.definitions,
        }
        return CliBinding(runtime, stack, tuple(sorted(audit_names)))
    except BaseException:
        if not stack.frames:
            stack = FrameStack(tuple(frames))
        with suppress(Exception):
            await stack.close()
        raise
