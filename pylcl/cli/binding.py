"""Layered CLI Frame construction and reverse-order ownership."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

from pylcl.api import LCL_RUNTIME
from pylcl.ast import LclAstNode, LclConstant
from pylcl.cli.commands import Command
from pylcl.cli.models import CliConfig, CliParams
from pylcl.cli.parser import lazy_override_expression
from pylcl.config import load_config
from pylcl.errors import LclCliUsageError
from pylcl.runtime import Frame, Module
from pylcl.types import ModuleName

# Module label for the call-specific preset/import layer.
IMPORTS_MODULE_NAME = ModuleName("LCL_IMPORTS")
# Module label for command and logger defaults.
DEFAULTS_MODULE_NAME = ModuleName("command_defaults")
# Module label used when no configuration file is selected.
EMPTY_CONFIG_MODULE_NAME = ModuleName("empty_config")
# Module label for raw CLI overrides.
OVERRIDES_MODULE_NAME = ModuleName("cli_overrides")
# Module label for the handler-visible runtime layer.
RUNTIME_MODULE_NAME = ModuleName("cli_runtime")


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
    """

    frame: Frame
    stack: FrameStack


def default_definitions(command: Command, cli_config: CliConfig) -> dict[str, LclAstNode]:
    """Build constant command and logger default definitions.

    :param command: Selected command declaration.
    :param cli_config: Framework defaults.
    :returns: Fresh definition mapping.
    """
    log_config = cli_config.log_config
    definitions: dict[str, LclAstNode] = {
        "log_dir": LclConstant(value=log_config.log_dir),
        "log_file_name": LclConstant(value=log_config.log_file_name),
        "log_level": LclConstant(value=log_config.log_level),
        "log_format": LclConstant(value=log_config.log_format),
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
    try:
        imports = LCL_RUNTIME.derive(Module(IMPORTS_MODULE_NAME, {}), dict(command.preset))
        frames.append(imports)
        defaults_module = Module(DEFAULTS_MODULE_NAME, default_definitions(command, cli_config))
        defaults = imports.derive(defaults_module)
        frames.append(defaults)
        if params.config_file_path is None:
            config_module = Module(EMPTY_CONFIG_MODULE_NAME, {})
        else:
            config_module = (await load_config(params.config_file_path)).to_module()
        config = defaults.derive(config_module)
        frames.append(config)
        override_definitions: dict[str, LclAstNode] = {}
        override_values: dict[str, object] = {}
        for name, value in params.overrides.items():
            if isinstance(value, bool):
                override_values[name] = value
                continue
            expression = lazy_override_expression(value)
            if expression is None:
                override_values[name] = value
            else:
                override_definitions[name] = expression
        runtime_values: dict[str, object] = {
            **override_values,
            "as_of_date": params.as_of_date,
            "dryrun": params.dryrun,
            "cli_params": params,
        }
        overrides = config.derive(
            Module(OVERRIDES_MODULE_NAME, override_definitions),
            runtime_values,
        )
        frames.append(overrides)
        runtime = overrides.derive(Module(RUNTIME_MODULE_NAME, {}))
        frames.append(runtime)
        stack = FrameStack(tuple(frames))
        missing = [
            item.name
            for item in command.parameter_docs
            if item.required and not runtime.has(item.name)
        ]
        if missing:
            raise LclCliUsageError("missing required parameter: " + ", ".join(missing))
        return CliBinding(runtime, stack)
    except BaseException:
        if not stack.frames:
            stack = FrameStack(tuple(frames))
        with suppress(Exception):
            await stack.close()
        raise
