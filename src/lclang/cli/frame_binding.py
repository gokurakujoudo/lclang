"""Layered CLI Frame construction and reverse-order ownership.

Defines ``CliBinding``, ``default_definitions``, ``build_binding``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from lclang.cli.binding_override import partition_overrides, require_forced_result
from lclang.cli.cli_models import CliConfig, CliParams
from lclang.cli.command_definition import Command
from lclang.cli.frame_stack import FrameStack as FrameStack
from lclang.cli.invocation_key import (
    RUNTIME_AS_OF_DATE_KEY,
    RUNTIME_CLI_PARAMS_KEY,
    RUNTIME_COMMAND_KEY,
    RUNTIME_DRYRUN_KEY,
    RUNTIME_EXECUTION_TIMESTAMP_KEY,
    RUNTIME_VERBOSE_KEY,
    RUNTIME_YMD_KEY,
)
from lclang.cli.logger_parameter import collect_borrowed_console_values, logger_definitions
from lclang.cli.parameter_metadata import DerivedParameterDoc, get_parameter_masks
from lclang.common.identifiers import ModuleName
from lclang.config import load_config
from lclang.error import CliErrorCode, LclCliError, LclCliUsageError
from lclang.error.exception_base import LclValidationError
from lclang.error.failure_aggregation import combine_failures
from lclang.error.operation_guard import guard_async_failure, guard_constructor, guard_failure
from lclang.lang.ast import LclAstNode, LclConstant
from lclang.lang.runtime import Frame, Module
from lclang.lang.runtime.frame.default_frame_scope import attach_defaults, create_default_frame
from lclang.lang.runtime.module_frame_factory import LCL_RUNTIME

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


@guard_constructor(LclValidationError, CliErrorCode.E41_CLI_BINDING_NATIVE_FAILURE)
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


@guard_failure(LclCliError, CliErrorCode.E41_CLI_BINDING_NATIVE_FAILURE)
def default_definitions(command: Command, cli_config: CliConfig) -> dict[str, LclAstNode]:
    """Build constant command and logger default definitions.

    :param command: Selected command declaration.
    :param cli_config: Framework defaults.
    :returns: Fresh definition mapping.
    """
    definitions = logger_definitions(cli_config.log_config)
    definitions.update(
        {
            parameter.name: LclConstant(value=parameter.default)
            for parameter in command.parameter_docs
            if parameter.default is not None
        }
    )
    return definitions


@guard_async_failure(LclCliError, CliErrorCode.E41_CLI_BINDING_NATIVE_FAILURE)
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
        if command.default_bindings:
            variable_defaults = create_default_frame(command.default_bindings)
            frames.insert(0, variable_defaults)
            attach_defaults(imports, variable_defaults)
        defaults_module = Module(
            DEFAULTS_MODULE_NAME,
            default_definitions(command, cli_config),
            masked_names=frozenset(
                item.name
                for item in command.parameter_docs
                if item.masked and item.default is not None
            ),
        )
        if params.config_file_path is None:
            config_module = Module(EMPTY_CONFIG_MODULE_NAME, {})
        else:
            config_module = (
                await load_config(
                    params.config_file_path,
                    overrides=using_overrides,
                )
            ).to_module()
        combined = defaults_module.mixin(config_module).mixin(
            Module(
                OVERRIDES_MODULE_NAME,
                {
                    **{key: LclConstant(value=value) for key, value in preliminary_values.items()},
                    **preliminary_definitions,
                },
                masked_names=params.masked_names,
            ),
            name=str(config_module.name),
        )
        borrowed_values = collect_borrowed_console_values(
            defaults_module.definitions, combined.definitions
        )
        definitions = {
            key: node
            for key, node in combined.definitions.items()
            if key not in preliminary_values and key not in borrowed_values
        }
        config = imports.derive(
            Module(
                combined.name,
                definitions,
                masked_names=combined.masked_names & definitions.keys(),
                namespace_names=combined.namespace_names,
            ),
            {**borrowed_values, **preliminary_values, **execution_values},
            masked_names=combined.masked_names | params.masked_names,
        )
        frames.append(config)
        strict_result = command.name in {"parse_lcl", "eval_lcl"} and (
            params.overrides.get("FORCE") is True
        )
        if strict_result:
            require_forced_result(params, preliminary_definitions, config)
        runtime = config.derive(
            Module(RUNTIME_MODULE_NAME, {}),
            masked_names=get_parameter_masks(command.parameter_docs, config),
        )
        frames.append(runtime)
        stack = FrameStack(tuple(frames))
        missing = [
            item.name
            for item in command.parameter_docs
            if item.required
            and not isinstance(item, DerivedParameterDoc)
            and not runtime.has(item.name)
        ]
        if missing:
            raise LclCliUsageError(
                "missing required parameter: " + ", ".join(missing),
                code=CliErrorCode.E41_MISSING_REQUIRED_PARAMETER_JOIN_MISSING,
            )
        audit_names = {
            *(item.name for item in command.parameter_docs),
            *config_module.definitions,
        }
        return CliBinding(runtime, stack, tuple(sorted(audit_names)))
    except BaseException as error:
        if not stack.frames:
            stack = FrameStack(tuple(frames))
        try:
            await stack.close()
        except BaseException as cleanup:
            failure = combine_failures(
                error, cleanup, code=CliErrorCode.E41_BINDING_CLEANUP_FAILURE
            )
            raise failure from failure.__cause__
        raise
