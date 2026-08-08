"""Public Frame close state and deterministic cleanup API."""

from __future__ import annotations

from typing import Protocol, cast

from pylcl.runtime.frame.lifecycle import _FrameLifecycle


class ClosableFrame(Protocol):
    """Describe lifecycle state required by public cleanup operations.

    .. note::
       The protocol deliberately excludes caches and evaluation implementation.
    """

    _lifecycle: _FrameLifecycle


class FrameClosingApi:
    """Expose lifecycle status and cleanup for a concrete Frame.

    .. note::
       Concrete Frames retain the lifecycle object and all resource ownership.
    """

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
