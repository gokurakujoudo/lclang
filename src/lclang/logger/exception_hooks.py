"""Validated opt-in installation of unhandled LCL exception reports.

Defines ``install_exception_hooks``.
"""

import asyncio
from typing import Literal

from lclang.error import LclLoggerError, LclValidationError, LoggerErrorCode
from lclang.error.operation_guard import guard_failure
from lclang.logger.exception_hook_installation import EXCEPTION_HOOK_LOCK, ExceptionHookInstallation
from lclang.logger.traceback_policy import validate_traceback_style


@guard_failure(LclLoggerError, LoggerErrorCode.E23_EXCEPTION_HOOK_INSTALLATION_NATIVE_FAILURE)
def install_exception_hooks(
    *,
    traceback_style: Literal["compact", "full"] = "compact",
    include_threads: bool = True,
    loop: asyncio.AbstractEventLoop | None = None,
) -> ExceptionHookInstallation:
    """Install stderr reports while preserving native propagation and prior hooks.

    :param traceback_style: Compact language-frame filtering or full Python frames.
    :param include_threads: Boolean opt-in for worker threads, enabled by default.
    :param loop: Explicit caller-owned loop; install and restore on its owning thread.
    :returns: Installation whose idempotent restore preserves later hook replacements.
    :raises LclValidationError: If policy, Boolean flag or loop is invalid.
    :raises LclLoggerError: If native hook installation fails.
    """
    style = validate_traceback_style(traceback_style)
    if not isinstance(include_threads, bool):
        raise LclValidationError(
            "include_threads must be Boolean", code=LoggerErrorCode.E23_EXCEPTION_HOOK_THREADS_TYPE
        )
    if loop is not None and not isinstance(loop, asyncio.AbstractEventLoop):
        raise LclValidationError(
            "loop must be an AbstractEventLoop or None",
            code=LoggerErrorCode.E23_EXCEPTION_HOOK_LOOP_TYPE,
        )
    with EXCEPTION_HOOK_LOCK:
        installation = ExceptionHookInstallation(style, include_threads, loop)
        installation.activate()
    return installation
