"""Own and settle all invocation-created Frames during reverse cleanup."""

from dataclasses import dataclass

from lclang.error import LclCliError, LclValidationError
from lclang.error.aggregation import combine_failures
from lclang.error.boundary import guard_async_failure, guard_constructor
from lclang.error.codes.cli import Code as cli_codes
from lclang.error.waiting import settle_cleanup
from lclang.runtime import Frame


@guard_constructor(LclValidationError, cli_codes.NATIVE_441)
@dataclass(slots=True)
class FrameStack:
    """Own invocation-created Frames in parent-to-child order.

    :param frames: Frames to close in reverse order.
    :param closed: Whether close has completed or begun.
    """

    frames: tuple[Frame, ...]
    closed: bool = False

    @guard_async_failure(LclCliError, cli_codes.NATIVE_441)
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
                frame.close(), error_type=LclCliError, code=cli_codes.FRAME_CLOSE_FAILURE
            )
            if failure is not None:
                pending = combine_failures(
                    pending, failure, code=cli_codes.MULTIPLE_CLEANUP_FAILURES
                )
        if pending is not None:
            raise pending from pending.__cause__
