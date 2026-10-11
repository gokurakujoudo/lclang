"""Explicit ownership of main-thread, worker-thread and selected-loop hooks.

Defines ``ExceptionHookInstallation``, ``EXCEPTION_HOOK_LOCK``.
"""

import asyncio
import sys
import threading
from collections.abc import Callable
from types import MethodType, TracebackType
from typing import Literal, cast

from lclang.error.exception_report import contains_lcl_failure, render_exception_report
from lclang.utils.value_representation import safe_repr

# One process owns these stdlib hook attributes; the lock also prevents interleaved reports.
EXCEPTION_HOOK_LOCK = threading.RLock()

type SystemExceptionHook = Callable[
    [type[BaseException], BaseException, TracebackType | None], object
]
type ThreadExceptionHook = Callable[[threading.ExceptHookArgs], object]
type LoopExceptionHook = Callable[[asyncio.AbstractEventLoop, dict[str, object]], object]


class ExceptionHookInstallation:
    """Own an explicit hook installation until :meth:`restore` is called.

    :param traceback_style: Validated compact or full Python frame policy.
    :param include_threads: Whether the worker-thread hook is owned too.
    :param loop: Optional caller-owned loop; it is never started or closed here.
    """

    def __init__(
        self,
        traceback_style: Literal["compact", "full"],
        include_threads: bool,
        loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        """Capture previous handlers without installing anything.

        :param traceback_style: Validated traceback policy.
        :param include_threads: Validated worker-thread selection.
        :param loop: Explicit caller-owned loop or None.
        """
        self.traceback_style: Literal["compact", "full"] = traceback_style
        self.include_threads = include_threads
        self.loop = loop
        self.active = False
        self.previous_system: SystemExceptionHook = sys.excepthook
        self.previous_thread: ThreadExceptionHook = threading.excepthook
        self.previous_loop: LoopExceptionHook | None = (
            None if loop is None else loop.get_exception_handler()
        )
        self.system_hook: SystemExceptionHook = self.report_system_exception
        self.thread_hook: ThreadExceptionHook = self.report_thread_exception
        self.loop_hook: LoopExceptionHook = self.report_loop_exception

    def activate(self) -> None:
        """Install selected handlers after complete public input validation.

        :raises Exception: If the supplied loop rejects installation.
        """
        with EXCEPTION_HOOK_LOCK:
            if self.loop is not None:
                self.loop.set_exception_handler(self.loop_hook)
            sys.excepthook = self.system_hook
            if self.include_threads:
                threading.excepthook = self.thread_hook
            self.active = True

    def restore(self) -> None:
        """Restore owned attributes once, preserving later third-party replacements."""
        with EXCEPTION_HOOK_LOCK:
            if not self.active:
                return
            self.active = False
            if sys.excepthook is self.system_hook:
                sys.excepthook = cast(
                    SystemExceptionHook,
                    self.select_previous_hook(self.previous_system, "previous_system"),
                )
            if self.include_threads and threading.excepthook is self.thread_hook:
                threading.excepthook = cast(
                    ThreadExceptionHook,
                    self.select_previous_hook(self.previous_thread, "previous_thread"),
                )
            if self.loop is not None and self.loop.get_exception_handler() is self.loop_hook:
                self.loop.set_exception_handler(
                    cast(
                        LoopExceptionHook | None,
                        self.select_previous_hook(self.previous_loop, "previous_loop"),
                    )
                )

    def select_previous_hook(self, hook: object, attribute: str) -> object:
        """Skip closed installations when restoring out of stack order.

        :param hook: Previously captured callback or default-loop sentinel.
        :param attribute: Saved callback field for this hook kind.
        :returns: First still-active callback or the original native handler.
        """
        while (
            isinstance(hook, MethodType)
            and isinstance(hook.__self__, ExceptionHookInstallation)
            and not hook.__self__.active
        ):
            hook = getattr(hook.__self__, attribute)
        return hook

    def write_report(
        self, error: BaseException, tb: TracebackType | None, context: str = ""
    ) -> bool:
        """Write one synchronous protected report or request delegation.

        :param error: Exception selected by the owning stdlib hook.
        :param tb: Original traceback provided by that hook.
        :param context: Optional thread or loop boundary description.
        :returns: Whether reporting succeeded and consumed this display boundary.
        """
        if not self.active or not contains_lcl_failure(error):
            return False
        try:
            text = render_exception_report(error, tb, traceback_style=self.traceback_style)
            if context:
                text = safe_repr(context, renderer=str) + "\n" + text
            with EXCEPTION_HOOK_LOCK:
                sys.stderr.write(text + "\n")
                sys.stderr.flush()
            return True
        except Exception:
            return False

    def report_system_exception(
        self, error_type: type[BaseException], error: BaseException, tb: TracebackType | None
    ) -> None:
        """Report an ordinary LCL chain or delegate to the captured main hook.

        :param error_type: Native exception type supplied by Python.
        :param error: Original uncaught exception.
        :param tb: Original traceback supplied by Python.
        """
        if not self.write_report(error, tb):
            self.previous_system(error_type, error, tb)

    def report_thread_exception(self, args: threading.ExceptHookArgs) -> None:
        """Report an ordinary LCL worker failure without retaining its thread.

        :param args: Native hook arguments, borrowed for this call only.
        """
        name = "unknown" if args.thread is None else args.thread.name
        if args.exc_value is None or not self.write_report(
            args.exc_value, args.exc_traceback, "Unhandled exception in thread " + name
        ):
            self.previous_thread(args)

    def report_loop_exception(
        self, loop: asyncio.AbstractEventLoop, context: dict[str, object]
    ) -> None:
        """Report an explicit loop's LCL failure or preserve its prior handler.

        :param loop: Original caller-owned event loop.
        :param context: Borrowed native asyncio exception context.
        """
        error = context.get("exception")
        message = safe_repr(context.get("message", "Unhandled event-loop exception"), renderer=str)
        if isinstance(error, BaseException) and self.write_report(
            error, error.__traceback__, message
        ):
            return
        if self.previous_loop is None:
            loop.default_exception_handler(context)
        else:
            self.previous_loop(loop, context)
