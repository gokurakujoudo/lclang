"""Frame lifecycle state, cache ownership, and resource cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lclang.error import LclEvaluationError
from lclang.error.aggregation import combine_failures
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.runtime import Code as runtime_codes
from lclang.error.wrapping import wrap_failure

if TYPE_CHECKING:
    pass

import asyncio
from collections.abc import Callable

from lclang.error import LclClosedFrameError
from lclang.lang.evaluator.awaitables import resolve_awaitable
from lclang.source import SourceSpan

# Unitless unique sentinel distinguishes an absent cache entry from every valid cached value,
# including None.
_MISSING = object()


@guard_constructor(LclValidationError, runtime_codes.NATIVE_236)
class InternalFrameLifecycle:
    """Own Frame cache commits, closure state, and resource retirement.

    .. note::
       Results are snapshots; replacement retires prior closeable values.
    """

    def __init__(
        self,
        results: dict[str, object],
        failures: dict[str, Exception],
        inflight: dict[str, asyncio.Task[object]],
        refreshes: dict[str, asyncio.Task[object]],
        clear_dependencies: Callable[[], None],
    ) -> None:
        """Attach mutable Frame-owned state without copying it.

        :param results: Successful definition snapshots.
        :param failures: Failed definition snapshots.
        :param inflight: Active initial evaluation tasks.
        :param refreshes: Active recalculation tasks.
        :param clear_dependencies: Callback clearing committed traces.
        """
        self.results = results
        self.failures = failures
        self.inflight = inflight
        self.refreshes = refreshes
        self.clear_dependencies = clear_dependencies
        self.retired: list[object] = []
        self.closing = False
        self.closed = False
        self.close_task: asyncio.Task[None] | None = None

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_236)
    def ensure_open(self, span: SourceSpan | None) -> None:
        """Reject operations once closing has begun.

        :param span: Optional source location for the lifecycle error.
        :raises LclClosedFrameError: If the Frame is closing or closed.
        """
        if self.closing or self.closed:
            raise LclClosedFrameError(
                "Frame is closed", span=span, code=runtime_codes.E36_FRAME_IS_CLOSED
            )

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_236)
    def commit_result(self, name: str, result: object) -> None:
        """Publish one successful snapshot and retire its replacement.

        :param name: Evaluated definition name.
        :param result: Successful value to cache.
        """
        previous = self.results.get(name, _MISSING)
        if previous is not _MISSING and previous is not result:
            self.retired.append(previous)
        self.results[name] = result
        self.failures.pop(name, None)

    @guard_failure(LclEvaluationError, runtime_codes.NATIVE_236)
    def commit_failure(self, name: str, error: Exception) -> None:
        """Publish one failed snapshot and retire any successful value.

        :param name: Evaluated definition name.
        :param error: Failure to cache for later requests.
        """
        previous = self.results.pop(name, _MISSING)
        if previous is not _MISSING:
            self.retired.append(previous)
        self.failures[name] = error

    @guard_async_failure(LclEvaluationError, runtime_codes.NATIVE_236)
    async def close(self) -> None:
        """Join or create the shielded single-flight close task."""
        task = self.close_task
        if task is None:
            self.closing = True
            task = asyncio.create_task(self.internal_run_close())
            self.close_task = task
        await asyncio.shield(task)

    async def internal_run_close(self) -> None:
        """Cancel work, close unique resources, and clear all owned state.

        :raises BaseException: If cleanup raises a non-Exception cancellation.
        :raises LclEvaluationError: If ordinary resource cleanup fails.
        """
        errors: list[BaseException] = []
        try:
            tasks = set(self.inflight.values())
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            resources = [*self.retired, *self.results.values()]
            seen: set[int] = set()
            for resource in reversed(resources):
                identity = id(resource)
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    await internal_close_resource(resource)
                except BaseException as cleanup_error:
                    errors.append(cleanup_error)
        finally:
            self.results.clear()
            self.failures.clear()
            self.inflight.clear()
            self.refreshes.clear()
            self.retired.clear()
            self.clear_dependencies()
            self.closing = False
            self.closed = True
        failure: BaseException | None = None
        for error in errors:
            cleanup = (
                wrap_failure(
                    error,
                    LclEvaluationError,
                    runtime_codes.RESOURCE_CLEANUP_FAILURE,
                    message="Frame cleanup failed",
                )
                if isinstance(error, Exception)
                else error
            )
            failure = combine_failures(
                failure, cleanup, code=runtime_codes.MULTIPLE_CLEANUP_FAILURES
            )
        if failure is not None:
            raise failure from failure.__cause__


async def internal_close_resource(resource: object) -> None:
    """Invoke one resource's asynchronous or synchronous close operation.

    :param resource: Opaque cached value that may expose ``aclose`` or ``close``.
    """
    operation: Callable[[], object] | None = None
    async_close = getattr(resource, "aclose", None)
    if callable(async_close):
        operation = async_close
    else:
        sync_close = getattr(resource, "close", None)
        if callable(sync_close):
            operation = sync_close
    if operation is not None:
        await resolve_awaitable(operation())
