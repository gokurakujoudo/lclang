"""Public Frame close state and deterministic cleanup API."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, cast

from lclang.runtime.frame.lifecycle import InternalFrameLifecycle


class ClosableFrame(Protocol):
    """Describe lifecycle state required by public cleanup operations.

    .. note::
       The protocol deliberately excludes caches and evaluation implementation.
    """

    _lifecycle: InternalFrameLifecycle


class FrameClosingApi:
    """Expose lifecycle status and cleanup for a concrete Frame.

    .. note::
       Concrete Frames retain the lifecycle object and all resource ownership.
    """

    async def __aenter__(self) -> Self:
        """Enter an owned Frame lifecycle scope.

        :returns: The same open Frame for evaluation inside the scope.
        """
        return self

    async def __aexit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the Frame when its asynchronous lifecycle scope exits.

        :param error_type: Exception type raised by the scope, when present.
        :param error: Exception raised by the scope, when present.
        :param traceback: Traceback associated with *error*, when present.
        :returns: ``None`` so an exception from the scope is never suppressed.
        :raises LclEvaluationError: If an owned resource cleanup fails.
        :raises BaseException: If cleanup itself raises a direct base exception.
        """
        await self.close()

    @property
    def closed(self) -> bool:
        """Return whether owned cleanup has completely settled.

        :returns: ``True`` only after the shared close Task finishes.

        .. note::
           Requests are rejected while closing even though this remains false.
        """
        return cast(ClosableFrame, self)._lifecycle.closed

    async def close(self) -> None:
        """Cancel owned work and release cached resources exactly once.

        :returns: ``None`` after the shared close outcome settles.
        :raises LclEvaluationError: If an owned resource cleanup fails.
        :raises BaseException: If cleanup itself raises a direct base exception.

        .. note::
           Cancelling one caller does not cancel the owned close Task.
        """
        await cast(ClosableFrame, self)._lifecycle.close()
