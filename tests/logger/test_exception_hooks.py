"""Explicit hooks retain propagation state and safely delegate other failures."""

import asyncio
import io
import sys
import threading
from contextlib import redirect_stderr
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest

from lclang.error import LclError, LclErrorGroup, LclLoggerError, LclValidationError
from lclang.logger import install_exception_hooks


def test_system_hook_formats_lcl_and_delegates_native_and_control() -> None:
    """The replacement keeps cause and traceback objects while leaving native hooks intact."""
    original = sys.excepthook
    delegated = Mock()
    with patch.object(sys, "excepthook", delegated):
        installation = install_exception_hooks(include_threads=False)
        try:
            try:
                raise LclError("application failure", code="APP/FAILED") from ValueError("cause")
            except LclError as error:
                trace, cause = error.__traceback__, error.__cause__
                output = io.StringIO()
                with redirect_stderr(output):
                    sys.excepthook(type(error), error, trace)
                assert "[APP/FAILED: cause]" in output.getvalue()
                assert "Operation: application failure" in output.getvalue()
                assert "test_exception_hooks.py" in output.getvalue()
                assert error.__traceback__ is trace and error.__cause__ is cause
            for native in (
                ValueError("native"),
                KeyboardInterrupt(),
                StopIteration(),
                BaseExceptionGroup("mixed", [LclError("LCL"), SystemExit()]),
            ):
                sys.excepthook(type(native), native, None)
            assert delegated.call_count == 4
        finally:
            installation.restore()
            installation.restore()
        assert sys.excepthook is delegated
    assert sys.excepthook is original


def test_nested_restore_skips_closed_hooks_and_preserves_replacements() -> None:
    """Out-of-order restoration cannot revive an earlier installation."""
    original_system, original_thread = sys.excepthook, threading.excepthook
    first = install_exception_hooks()
    second = install_exception_hooks()
    first.restore()
    assert sys.excepthook is second.system_hook
    second.restore()
    assert sys.excepthook is original_system and threading.excepthook is original_thread
    replacement = Mock()
    installation = install_exception_hooks()
    try:
        sys.excepthook = replacement
        threading.excepthook = replacement
        installation.restore()
        assert sys.excepthook is replacement and threading.excepthook is replacement
    finally:
        sys.excepthook, threading.excepthook = original_system, original_thread


def test_retained_closed_wrapper_and_failed_output_delegate() -> None:
    """A retained callback is inert after restore and report failures use the previous hook."""
    previous = Mock()
    with patch.object(sys, "excepthook", previous):
        installation = install_exception_hooks()
        error: LclError = LclError("failed")
        with patch(
            "lclang.logger.exception_hook_installation.render_exception_report",
            side_effect=OSError("renderer"),
        ):
            installation.system_hook(type(error), error, None)
        with patch.object(sys, "stderr") as stream:
            stream.write.side_effect = OSError("stream")
            installation.system_hook(type(error), error, None)
        installation.restore()
        installation.system_hook(type(error), error, None)
        assert previous.call_count == 3


def test_worker_hook_reports_thread_context_and_delegates_native() -> None:
    """Worker threads use the same tree without holding thread objects after reporting."""
    previous = Mock()
    with patch.object(threading, "excepthook", previous):
        installation = install_exception_hooks()
        try:
            error: LclError = LclError("worker failed")
            output = io.StringIO()
            with redirect_stderr(output):
                args = threading.ExceptHookArgs(
                    (type(error), error, None, threading.current_thread())
                )
                installation.thread_hook(args)
                installation.thread_hook(threading.ExceptHookArgs((type(error), error, None, None)))
            assert "MainThread" in output.getvalue() and "thread unknown" in output.getvalue()
            native = ValueError("native")
            installation.thread_hook(threading.ExceptHookArgs((type(native), native, None, None)))
            assert previous.call_count == 1
        finally:
            installation.restore()


def test_selected_loop_reports_lcl_and_restores_prior_handler() -> None:
    """Only the explicit loop is touched; native and context-only events retain delegation."""
    loop = asyncio.new_event_loop()
    other = asyncio.new_event_loop()
    previous = Mock()
    loop.set_exception_handler(previous)
    installation = install_exception_hooks(loop=loop)
    try:
        error = LclErrorGroup("group", [LclError("member")])
        output = io.StringIO()
        with redirect_stderr(output):
            loop.call_exception_handler({"exception": error, "message": "Task failed"})
        assert "Task failed" in output.getvalue() and "Failure 1" in output.getvalue()
        loop.call_exception_handler({"exception": ValueError("native")})
        loop.call_exception_handler({"message": "only context"})
        assert previous.call_count == 2 and other.get_exception_handler() is None
    finally:
        installation.restore()
        assert loop.get_exception_handler() is previous
        loop.close()
        other.close()


def test_default_loop_delegation_and_nested_loop_restore() -> None:
    """Closed installations are skipped for the loop sentinel as well as native hooks."""
    loop = asyncio.new_event_loop()
    first = install_exception_hooks(loop=loop)
    second = install_exception_hooks(loop=loop)
    try:
        with patch.object(loop, "default_exception_handler") as default:
            loop.call_exception_handler({"message": "native context"})
            assert default.call_args.args[0]["message"] == "native context"
        first.restore()
        second.restore()
        assert loop.get_exception_handler() is None
    finally:
        first.restore()
        second.restore()
        loop.close()


@pytest.mark.parametrize(
    "options",
    [
        {"include_threads": 1},
        {"loop": object()},
        {"traceback_style": 1},
        {"traceback_style": "bad"},
    ],
)
def test_invalid_installation_does_not_change_hooks(options: dict[str, object]) -> None:
    """Validation is complete before touching any process-global handler."""
    original = sys.excepthook
    with pytest.raises(LclValidationError):
        install_exception_hooks(**cast(Any, options))
    assert sys.excepthook is original


def test_loop_installation_failure_keeps_global_hooks() -> None:
    """A native loop failure is coded without leaving partially installed global hooks."""
    loop = asyncio.new_event_loop()
    original = sys.excepthook
    try:
        with (
            patch.object(loop, "set_exception_handler", side_effect=OSError("rejected")),
            pytest.raises(LclLoggerError) as caught,
        ):
            install_exception_hooks(loop=loop)
        assert isinstance(caught.value.__cause__, OSError)
        assert sys.excepthook is original
    finally:
        loop.close()
