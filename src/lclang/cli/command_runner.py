"""CLI routing before configuration and process logger initialization.

Defines ``script_label_from_args``, ``run_command``, ``run_entrance``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import replace

from lclang.cli.argv_adapter import ArgvParts, split_argv
from lclang.cli.cli_models import CliConfig, CliResultStatus
from lclang.cli.command_definition import Command
from lclang.cli.command_entrance import CliEntrance
from lclang.cli.command_execution import execute_command
from lclang.cli.command_routing import RouteAction, route_command
from lclang.cli.help_rendering import render_command_help, render_group_help, render_usage_error
from lclang.cli.option_parser import help_requested, parse_cli_params
from lclang.common.binding_mask import normalize_masked_mapping
from lclang.error import CliErrorCode, LclCliError, RouteFailure
from lclang.error.exception_base import LclStateError
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure
from lclang.error.operation_guard import guard_async_failure, guard_failure


@guard_failure(LclCliError, CliErrorCode.E52_COMMAND_RUNNER_NATIVE_FAILURE)
def script_label_from_args(args: Sequence[str] | None) -> str:
    """Return a best-effort label for pre-parse usage failures.

    :param args: Optional explicit full argv.
    :returns: Script basename or stable fallback.
    """
    if args is not None and len(args) > 1 and isinstance(args[1], str):
        return args[1].replace("\\", "/").rsplit("/", 1)[-1]
    return "script.py"


@guard_async_failure(LclCliError, CliErrorCode.E52_COMMAND_RUNNER_NATIVE_FAILURE)
async def run_command(command: Command, args: Sequence[str] | None = None) -> int:
    """Run one command directly from full argv.

    :param command: Command to execute without group routing.
    :param args: Full argv, or ``None`` for process adaptation.
    :returns: Integer command status.
    """
    try:
        parts = split_argv(args)
        tokens = parts.tokens[1:] if parts.tokens[:1] == (command.name,) else parts.tokens
        if help_requested(tokens):
            print(render_command_help(parts.script_label, command, (command.name,)), end="")
            return 0
        params = parse_cli_params(parts, (command.name,), tokens)
        return await execute_command(command, params, CliConfig())
    except Exception as error:
        if not is_ordinary_failure(error):
            raise
        error = wrap_failure(error, LclCliError, CliErrorCode.E52_COMMAND_RUNNER_NATIVE_FAILURE)
        label = script_label_from_args(args)
        help_text = render_command_help(label, command, (command.name,))
        print(render_usage_error(str(error), help_text), file=sys.stderr, end="")
        return int(CliResultStatus.EXCEPTION)


@guard_async_failure(LclCliError, CliErrorCode.E52_COMMAND_RUNNER_NATIVE_FAILURE)
async def run_entrance(entrance: CliEntrance, args: Sequence[str] | None = None) -> int:
    """Route and execute one entrance from full argv.

    :param entrance: Root group, version, and framework defaults.
    :param args: Full argv, or ``None`` for process adaptation.
    :returns: Integer program status.
    :raises LclStateError: Internally converted if routing yields no command.
    """
    parts: ArgvParts | None = None
    try:
        parts = split_argv(args)
        route = route_command(entrance.command_group, parts.tokens)
        if route.action is RouteAction.HELP:
            help_text = render_group_help(
                parts.script_label,
                route.group,
                route.path,
                not route.path,
            )
            print(help_text, end="")
            return 0
        if route.action is RouteAction.VERSION:
            print(f"{parts.script_label} {entrance.version}")
            return 0
        command = route.command
        if command is None:
            raise LclStateError(
                "command route did not select a command",
                code=CliErrorCode.E52_COMMAND_ROUTE_DID_NOT_SELECT_A_COMMAND,
            )
        values, masked_names = normalize_masked_mapping(entrance.lcl_mixin)
        command = replace(
            command,
            preset={**values, **command.preset},
            masked_names=masked_names | command.masked_names,
        )
        if help_requested(route.remaining):
            print(render_command_help(parts.script_label, command, route.path), end="")
            return 0
        params = parse_cli_params(parts, route.path, route.remaining)
        return await execute_command(command, params, entrance.cli_config)
    except RouteFailure as error:
        label = script_label_from_args(args) if parts is None else parts.script_label
        help_text = render_group_help(label, error.group, error.path, not error.path)
        print(render_usage_error(str(error), help_text), file=sys.stderr, end="")
        return int(CliResultStatus.EXCEPTION)
    except Exception as error:
        if not is_ordinary_failure(error):
            raise
        error = wrap_failure(error, LclCliError, CliErrorCode.E52_COMMAND_RUNNER_NATIVE_FAILURE)
        label = script_label_from_args(args) if parts is None else parts.script_label
        help_text = render_group_help(label, entrance.command_group, (), True)
        print(render_usage_error(str(error), help_text), file=sys.stderr, end="")
        return int(CliResultStatus.EXCEPTION)
