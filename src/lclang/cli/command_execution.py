"""Command execution inside the unified process logger scope.

Defines ``write_result``, ``run_bound_command``, ``execute_command``.
"""

from __future__ import annotations

import logging
import sys

from lclang.cli.cli_models import CliConfig, CliParams, CliResult, CliResultStatus
from lclang.cli.command_definition import Command
from lclang.cli.exception_logging import report_command_failure
from lclang.cli.frame_binding import CliBinding, build_binding
from lclang.cli.invocation_audit import emit_execution_start
from lclang.cli.invocation_context import CliContext
from lclang.error import CliErrorCode, LclCliError, LclError, LclErrorGroup
from lclang.error.diagnostic_rendering import render_failure
from lclang.error.exception_base import LclValidationError
from lclang.error.failure_aggregation import combine_failures
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure
from lclang.error.operation_guard import guard_async_failure, guard_failure
from lclang.error.verbose_failure import trace_verbose_failure
from lclang.logger import Logger, resolve_logger_config, use_logger, use_logger_handler, use_verbose
from lclang.logger.record_formatter import FILE_ONLY_ATTRIBUTE


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
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


@guard_async_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
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
    action = "executing command"
    try:
        result = await command.handler(context)
        if not isinstance(result, CliResult):
            raise LclValidationError(
                "CLI command handler must return CliResult",
                code=CliErrorCode.E51_CLI_COMMAND_HANDLER_MUST_RETURN_CLIRESULT,
            )
    except BaseException as error:
        if not is_ordinary_failure(error):
            try:
                await binding.stack.close()
            except BaseException as control_cleanup:
                combined = combine_failures(
                    error, control_cleanup, code=CliErrorCode.E51_EXECUTION_CLEANUP_FAILURE
                )
                raise combined from combined.__cause__
            raise
        failure = wrap_failure(error, LclCliError, CliErrorCode.E51_HANDLER_FAILURE)
        pending = failure
        trace_verbose_failure(
            failure, "command execution", phase="executing command handler", stage="command"
        )
        result = CliResult(CliResultStatus.EXCEPTION, "")
    try:
        await binding.stack.close()
    except BaseException as error:
        if not is_ordinary_failure(error):
            if pending is not None:
                report_command_failure(logger, pending, action=action)
            combined = combine_failures(
                pending, error, code=CliErrorCode.E51_EXECUTION_CLEANUP_FAILURE
            )
            raise combined from combined.__cause__
        cleanup = wrap_failure(error, LclCliError, CliErrorCode.E51_CLEANUP_FAILURE)
        trace_verbose_failure(
            cleanup, "command cleanup", phase="closing command resources", stage="command"
        )
        cleanup_failure: LclError = (
            cleanup
            if pending is None
            else LclErrorGroup(
                "command execution and cleanup failed",
                [pending, cleanup],
                code=CliErrorCode.E51_EXECUTION_CLEANUP_FAILURE,
            )
        )
        pending = cleanup_failure
        action = "cleaning up command"
    if pending is not None:
        diagnostic = report_command_failure(logger, pending, action=action)
        result = CliResult(CliResultStatus.EXCEPTION, diagnostic)
        logged = True
    try:
        write_result(result, logger, log_result=not logged)
    except BaseException as error:
        if not is_ordinary_failure(error):
            combined = combine_failures(
                pending, error, code=CliErrorCode.E51_EXECUTION_CLEANUP_FAILURE
            )
            raise combined from combined.__cause__
        output_failure = wrap_failure(error, LclCliError, CliErrorCode.E51_OUTPUT_FAILURE)
        failure = (
            output_failure
            if pending is None
            else LclErrorGroup(
                "command output failed after another failure",
                [pending, output_failure],
                code=CliErrorCode.E51_EXECUTION_CLEANUP_FAILURE,
            )
        )
        trace_verbose_failure(
            output_failure, "command output", phase="writing command output", stage="command"
        )
        if pending is not None:
            reference = pending.verbose_failure_id or f"[{pending.code}]"
            output_failure.add_note(f"Earlier command failure: {reference}")
            trace_verbose_failure(
                failure,
                "combined command failures",
                phase="writing command output",
                stage="command",
            )
        output_diagnostic = report_command_failure(
            logger, output_failure, action="writing command output"
        )
        print(output_diagnostic, file=sys.stderr)
        diagnostic = render_failure(failure, action="writing command output")
        result = CliResult(CliResultStatus.EXCEPTION, diagnostic)
    return int(result.result_status)


@guard_async_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
async def execute_command(command: Command, params: object, cli_config: CliConfig) -> int:
    """Resolve logger configuration before creating the sole application scope.

    :param command: Selected command declaration.
    :param params: Parsed invocation values.
    :param cli_config: Framework defaults including declared logger settings.
    :returns: Process-compatible status after complete output drain.
    """
    if not isinstance(params, CliParams):
        invalid_params = LclValidationError(
            "CLI parameters must be CliParams", code=CliErrorCode.E51_PARAMETER_TYPE
        )
        print(render_failure(invalid_params, action="executing command"), file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    binding: CliBinding | None = None
    pending: BaseException | None = None
    status = int(CliResultStatus.EXCEPTION)
    try:
        binding = await build_binding(command, params, cli_config)
        config = await resolve_logger_config(binding.frame, params.verbose)
        async with use_logger_handler(config):
            logger = await use_logger(name=__name__)
            with use_verbose(logger, enabled=params.verbose):
                status = await run_bound_command(command, params, binding, logger)
    except BaseException as error:
        pending = error
    finally:
        if binding is not None:
            try:
                await binding.stack.close()
            except BaseException as error:
                pending = combine_failures(
                    pending, error, code=CliErrorCode.E51_EXECUTION_CLEANUP_FAILURE
                )
    if pending is not None:
        if not is_ordinary_failure(pending):
            raise pending
        failure = wrap_failure(pending, LclCliError, CliErrorCode.E51_HANDLER_FAILURE)
        diagnostic = render_failure(failure, action="executing command")
        print(diagnostic, file=sys.stderr)
        return int(CliResultStatus.EXCEPTION)
    return status
