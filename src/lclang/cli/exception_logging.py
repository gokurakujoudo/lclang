"""Single command-boundary exception reports with file-only Python stacks.

Defines ``report_command_failure``.
"""

from lclang.error import LclError
from lclang.error.diagnostic_rendering import render_failure
from lclang.error.verbose_failure import trace_verbose_failure
from lclang.logger import Logger
from lclang.logger.record_formatter import DIAGNOSTIC_ATTRIBUTE, FILE_ONLY_ATTRIBUTE


def report_command_failure(logger: Logger, failure: LclError, *, action: str) -> str:
    """Write a complete file report and return the single stderr diagnostic.

    :param logger: Active application logger owned by the CLI handler scope.
    :param failure: Original ordinary failure or final execution/cleanup group.
    :param action: Actual command boundary whose failure is being reported.
    :returns: Complete diagnostic for the existing result-output path.
    """
    if failure.verbose_failure_id is None:
        trace_verbose_failure(failure, action, phase=action, stage="command")
    diagnostic = render_failure(failure, action=action)
    logger.error(
        "%s",
        diagnostic,
        exc_info=(type(failure), failure, failure.__traceback__),
        extra={
            FILE_ONLY_ATTRIBUTE: True,
            DIAGNOSTIC_ATTRIBUTE: True,
            "lclang_failure_id": failure.verbose_failure_id,
        },
    )
    return diagnostic
