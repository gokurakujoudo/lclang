"""Command execution inside the unified process logger scope."""

from __future__ import annotations

import logging
import sys
from contextlib import suppress

from lclang.cli.audit import emit_execution_start
from lclang.cli.binding import CliBinding, build_binding
from lclang.cli.commands import Command
from lclang.cli.context import CliContext
from lclang.cli.logger_config import resolve_logger_config
from lclang.cli.models import CliConfig, CliParams, CliResult, CliResultStatus
from lclang.diagnostics import internal_verbose_scope
from lclang.logger import use_logger, use_logger_handler
from lclang.logger.formatter import FILE_ONLY_ATTRIBUTE
from lclang.logger.logger import Logger


def write_result(result: CliResult, logger: Logger, *, log_result: bool = True) -> None:
    """Keep command results separate from diagnostic console output.

    :param result: Validated command outcome.
    :param logger: Current process logger wrapper.
    :param log_result: Whether an exception record already described this outcome.
    """
    if not result.description:
        return
    success = result.result_status is CliResultStatus.SUCCESS
    print(result.description, file=sys.stdout if success else sys.stderr)
    if log_result:
        logger.log(
            logging.INFO if success else logging.ERROR,
            "%s",
            result.description,
            extra={FILE_ONLY_ATTRIBUTE: True},
        )


async def run_bound_command(
    command: Command, params: CliParams, binding: CliBinding, logger: Logger
) -> int:
    """Run a command and its resources while logging remains active.

    :param command: Selected command.
    :param params: Parsed invocation values.
    :param binding: Owned invocation Frame hierarchy.
    :param logger: Current process logger.
    :returns: Process-compatible result status.
    :raises BaseException: If cancellation or process control interrupts execution.
    """
    context = CliContext(params.as_of_date, params.dryrun, binding.frame, logger, params)
    emit_execution_start(logger, params, binding.frame, binding.execution_config_names)
    logged = False
    try:
        result = await command.handler(context)
        if not isinstance(result, CliResult):
            raise TypeError("CLI command handler must return CliResult")
    except Exception as error:
        logger.exception("command exception: %s", error)
        result = CliResult(CliResultStatus.EXCEPTION, str(error))
        logged = True
    except BaseException:
        with suppress(Exception):
            await binding.stack.close()
        raise
    try:
        await binding.stack.close()
    except Exception as error:
        logger.exception("command cleanup exception: %s", error)
        result = CliResult(CliResultStatus.EXCEPTION, str(error))
        logged = True
    try:
        write_result(result, logger, log_result=not logged)
    except Exception as error:
        logger.exception("command output exception: %s", error)
        result = CliResult(CliResultStatus.EXCEPTION, str(error))
    return int(result.result_status)


async def execute_command(command: Command, params: object, cli_config: CliConfig) -> int:
    """Resolve logger configuration before creating the sole application scope.

    :param command: Selected command declaration.
    :param params: Parsed invocation values.
    :param cli_config: Framework defaults including declared logger settings.
    :returns: Process-compatible status after complete output drain.
    """
    if not isinstance(params, CliParams):
        print("error: internal CLI params type mismatch", file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    binding: CliBinding | None = None
    try:
        binding = await build_binding(command, params, cli_config)
        config = await resolve_logger_config(binding.frame, params.verbose)
        async with use_logger_handler(config):
            logger = await use_logger(name=__name__)
            with internal_verbose_scope(logging.getLogger(__name__) if params.verbose else None):
                return await run_bound_command(command, params, binding, logger)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    finally:
        if binding is not None:
            with suppress(Exception):
                await binding.stack.close()
