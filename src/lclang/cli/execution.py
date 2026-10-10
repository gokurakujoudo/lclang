"""Command execution inside the unified process logger scope."""

from __future__ import annotations

import logging
import sys
from contextlib import suppress

from lclang.cli.audit import emit_execution_start
from lclang.cli.binding import CliBinding, build_binding
from lclang.cli.commands import Command
from lclang.cli.context import CliContext
from lclang.cli.models import CliConfig, CliParams, CliResult, CliResultStatus
from lclang.diagnostics import internal_verbose_scope
from lclang.error import LclCliError, LclError, LclErrorGroup
from lclang.error.aggregation import combine_failures
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_failure
from lclang.error.codes.cli import Code as cli_codes
from lclang.error.rendering import render_failure
from lclang.error.wrapping import wrap_failure
from lclang.logger import Logger, resolve_logger_config, use_logger, use_logger_handler
from lclang.logger.formatter import FILE_ONLY_ATTRIBUTE


@guard_failure(LclCliError, cli_codes.NATIVE_451)
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


@guard_async_failure(LclCliError, cli_codes.NATIVE_451)
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
    pending: LclError | None = None
    try:
        result = await command.handler(context)
        if not isinstance(result, CliResult):
            raise LclValidationError(
                "CLI command handler must return CliResult",
                code=cli_codes.E51_CLI_COMMAND_HANDLER_MUST_RETURN_CLIRESULT,
            )
    except Exception as error:
        failure = wrap_failure(error, LclCliError, cli_codes.HANDLER_FAILURE)
        pending = failure
        diagnostic = render_failure(failure, action="executing command")
        logger.exception("%s", diagnostic)
        result = CliResult(CliResultStatus.EXCEPTION, diagnostic)
        logged = True
    except BaseException as signal:
        try:
            await binding.stack.close()
        except BaseException as control_cleanup:
            combined = combine_failures(
                signal, control_cleanup, code=cli_codes.EXECUTION_CLEANUP_FAILURE
            )
            raise combined from combined.__cause__
        raise
    try:
        await binding.stack.close()
    except Exception as error:
        cleanup = wrap_failure(error, LclCliError, cli_codes.CLEANUP_FAILURE)
        cleanup_failure: LclError = (
            cleanup
            if pending is None
            else LclErrorGroup(
                "command execution and cleanup failed",
                [pending, cleanup],
                code=cli_codes.EXECUTION_CLEANUP_FAILURE,
            )
        )
        pending = cleanup_failure
        diagnostic = render_failure(cleanup_failure, action="cleaning up command")
        logger.exception("%s", diagnostic)
        result = CliResult(CliResultStatus.EXCEPTION, diagnostic)
        logged = True
    try:
        write_result(result, logger, log_result=not logged)
    except Exception as error:
        output_failure = wrap_failure(error, LclCliError, cli_codes.OUTPUT_FAILURE)
        failure = (
            output_failure
            if pending is None
            else LclErrorGroup(
                "command output failed after another failure",
                [pending, output_failure],
                code=cli_codes.EXECUTION_CLEANUP_FAILURE,
            )
        )
        diagnostic = render_failure(failure, action="writing command output")
        logger.exception("%s", diagnostic)
        result = CliResult(CliResultStatus.EXCEPTION, diagnostic)
    return int(result.result_status)


@guard_async_failure(LclCliError, cli_codes.NATIVE_451)
async def execute_command(command: Command, params: object, cli_config: CliConfig) -> int:
    """Resolve logger configuration before creating the sole application scope.

    :param command: Selected command declaration.
    :param params: Parsed invocation values.
    :param cli_config: Framework defaults including declared logger settings.
    :returns: Process-compatible status after complete output drain.
    """
    if not isinstance(params, CliParams):
        invalid_params = LclValidationError(
            "CLI parameters must be CliParams", code=cli_codes.PARAMETER_TYPE
        )
        print(render_failure(invalid_params, action="executing command"), file=sys.stderr)
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
        failure = wrap_failure(error, LclCliError, cli_codes.HANDLER_FAILURE)
        diagnostic = render_failure(failure, action="executing command")
        print(diagnostic, file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    finally:
        if binding is not None:
            with suppress(Exception):
                await binding.stack.close()
