"""Async CLI routing, execution, result output, and cleanup."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from contextlib import suppress

from pylcl.cli.binding import CliBinding, build_binding
from pylcl.cli.commands import Command
from pylcl.cli.context import CliContext
from pylcl.cli.entrance import CliEntrance
from pylcl.cli.help import render_command_help, render_group_help, render_usage_error
from pylcl.cli.logging import LoggerHandle, create_logger
from pylcl.cli.models import CliConfig, CliResult, CliResultStatus
from pylcl.cli.parser import help_requested, parse_cli_params
from pylcl.cli.process import ArgvParts, split_argv
from pylcl.cli.routing import RouteAction, RouteFailure, route_command


def write_result(
    result: CliResult,
    logger_handle: LoggerHandle,
    *,
    log_result: bool = True,
) -> None:
    """Print and optionally log one non-empty command result.

    :param result: Validated command result.
    :param logger_handle: Active command logger owner.
    :param log_result: Whether this result still needs a log record.
    :returns: ``None``.
    """
    if not result.description:
        return
    if result.result_status is CliResultStatus.SUCCESS:
        print(result.description, file=sys.stdout)
        if log_result:
            logger_handle.logger.info("%s", result.description)
    else:
        print(result.description, file=sys.stderr)
        if log_result:
            logger_handle.logger.error("%s", result.description)


async def close_after_control_flow(binding: CliBinding, logger_handle: LoggerHandle) -> None:
    """Best-effort close resources before propagating process-control failures.

    :param binding: Owned Frame hierarchy.
    :param logger_handle: Owned logger handlers.
    :returns: ``None``.
    """
    with suppress(Exception):
        await binding.stack.close()
    logger_handle.close()


async def execute_command(
    command: Command,
    params: object,
    cli_config: CliConfig,
) -> int:
    """Build context, invoke one handler, and map its complete outcome.

    :param command: Selected command declaration.
    :param params: Parsed :class:`CliParams` value.
    :param cli_config: Effective framework defaults.
    :returns: Integer status without leaking ordinary exceptions.
    :raises TypeError: Internally converted if the handler returns a wrong value.
    """
    from pylcl.cli.models import CliParams

    if not isinstance(params, CliParams):
        print("error: internal CLI params type mismatch", file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    try:
        binding = await build_binding(command, params, cli_config)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    try:
        logger_handle = await create_logger(binding.frame, str(id(binding.frame)))
    except Exception as error:
        with suppress(Exception):
            await binding.stack.close()
        print(f"error: {error}", file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    context = CliContext(
        params.as_of_date,
        params.dryrun,
        binding.frame,
        logger_handle.logger,
        params,
    )
    logged = False
    try:
        result = await command.handler(context)
        if not isinstance(result, CliResult):
            raise TypeError("CLI command handler must return CliResult")
    except Exception as error:
        logger_handle.logger.exception("command exception: %s", error)
        result = CliResult(CliResultStatus.EXCEPTION, str(error))
        logged = True
    except BaseException:
        await close_after_control_flow(binding, logger_handle)
        raise
    try:
        await binding.stack.close()
    except Exception as error:
        logger_handle.logger.exception("command cleanup exception: %s", error)
        result = CliResult(CliResultStatus.EXCEPTION, str(error))
        logged = True
    try:
        write_result(result, logger_handle, log_result=not logged)
    except Exception as error:
        logger_handle.logger.exception("command output exception: %s", error)
        result = CliResult(CliResultStatus.EXCEPTION, str(error))
    finally:
        logger_handle.close()
    return int(result.result_status)


def script_label_from_args(args: Sequence[str] | None) -> str:
    """Return a best-effort label for pre-parse usage failures.

    :param args: Optional explicit full argv.
    :returns: Script basename or stable fallback.
    """
    if args is not None and len(args) > 1 and isinstance(args[1], str):
        return args[1].replace("\\", "/").rsplit("/", 1)[-1]
    return "script.py"


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
        label = script_label_from_args(args)
        help_text = render_command_help(label, command, (command.name,))
        print(render_usage_error(str(error), help_text), file=sys.stderr, end="")
        return int(CliResultStatus.EXCEPTION)


async def run_entrance(entrance: CliEntrance, args: Sequence[str] | None = None) -> int:
    """Route and execute one entrance from full argv.

    :param entrance: Root group, version, and framework defaults.
    :param args: Full argv, or ``None`` for process adaptation.
    :returns: Integer program status.
    :raises RuntimeError: Internally converted if routing yields no command.
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
            raise RuntimeError("command route did not select a command")
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
        label = script_label_from_args(args) if parts is None else parts.script_label
        help_text = render_group_help(label, entrance.command_group, (), True)
        print(render_usage_error(str(error), help_text), file=sys.stderr, end="")
        return int(CliResultStatus.EXCEPTION)
