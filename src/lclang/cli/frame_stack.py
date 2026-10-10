"""Own and settle all invocation-created Frames during reverse cleanup.

Defines ``FrameStack``.
"""

from dataclasses import dataclass

from lclang.error import CliErrorCode, LclCliError, LclValidationError
from lclang.error.cleanup_wait import settle_cleanup
from lclang.error.failure_aggregation import combine_failures
from lclang.error.operation_guard import guard_async_failure, guard_constructor
from lclang.lang.runtime import Frame


@guard_constructor(LclValidationError, CliErrorCode.E41_CLI_BINDING_NATIVE_FAILURE)
@dataclass(slots=True)
class FrameStack:
    """Own invocation-created Frames in parent-to-child order.

    :param frames: Frames to close in reverse order.
    :param closed: Whether close has completed or begun.
    """

    frames: tuple[Frame, ...]
    closed: bool = False

    @guard_async_failure(LclCliError, CliErrorCode.E41_CLI_BINDING_NATIVE_FAILURE)
    async def close(self) -> None:
        """Close every owned Frame once in reverse order.

        :returns: ``None``.
        :raises LclCliError: If one Frame close fails.
        :raises LclErrorGroup: If several Frame closes fail.
        """
        if self.closed:
            return
        self.closed = True
        pending: BaseException | None = None
        for frame in reversed(self.frames):
            failure = await settle_cleanup(
                frame.close(), error_type=LclCliError, code=CliErrorCode.E41_FRAME_CLOSE_FAILURE
            )
            if failure is not None:
                pending = combine_failures(
                    pending, failure, code=CliErrorCode.E41_MULTIPLE_CLEANUP_FAILURES
                )
        if pending is not None:
            raise pending from pending.__cause__
