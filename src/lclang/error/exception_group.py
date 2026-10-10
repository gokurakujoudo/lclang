"""Structured ordinary failure groups with Python splitting semantics.

Defines ``LclErrorGroup``.
"""

from collections.abc import Sequence
from typing import Self

from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.exception_base import LclError, LclValidationError, copy_failure_state
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure


# ExceptionGroup owns a read-only C message descriptor; the shared LCL payload
# receives the remaining declared diagnostic fields through the copy hook.
class LclErrorGroup(ExceptionGroup, LclError):  # type: ignore[override]
    """Retain several ordinary failures as one structured diagnostic.

    :param message: Nonempty description of the combined failure.
    :param exceptions: Nonempty sequence of ordinary exceptions.
    :param code: Builtin aggregation code or application-defined code.
    :raises LclValidationError: If group metadata or members are invalid.
    """

    default_code = str(GeneralErrorCode.E21_GROUP)

    def __new__(
        cls,
        message: str,
        exceptions: Sequence[Exception],
        *,
        code: str = GeneralErrorCode.E21_GROUP,
    ) -> Self:
        """Validate and allocate a group with detached native-member wrappers.

        :param message: Nonempty combined failure description.
        :param exceptions: Ordinary failures to preserve.
        :param code: Diagnostic identifier for this group.
        :returns: Group preserving member order and each original cause.
        :raises LclValidationError: If the message, code or members are invalid.
        """
        record: LclError = LclError(message, code=code)
        if (
            not isinstance(exceptions, Sequence)
            or not exceptions
            or any(
                not isinstance(error, Exception) or not is_ordinary_failure(error)
                for error in exceptions
            )
        ):
            raise LclValidationError(
                "error group requires a nonempty sequence of ordinary exceptions",
                code=GeneralErrorCode.E21_GROUP_CONTENT,
            )
        members: list[LclError] = []
        for error in exceptions:
            if isinstance(error, LclError):
                members.append(error)
            else:
                members.append(wrap_failure(error, LclError, GeneralErrorCode.E21_GROUP_MEMBER))
        result = super().__new__(cls, message, members)
        record.copy_diagnostic_fields(result)
        return result

    def __init__(
        self,
        message: str,
        exceptions: Sequence[Exception],
        *,
        code: str = GeneralErrorCode.E21_GROUP,
    ) -> None:
        """Keep the state validated and installed during allocation.

        :param message: Combined description already stored by allocation.
        :param exceptions: Original member sequence already validated.
        :param code: Diagnostic identifier already installed.
        """

    # Python supplies ordinary members when splitting an ExceptionGroup. The
    # generic BaseExceptionGroup overload also advertises control-signal members.
    def derive(self, exceptions: Sequence[Exception]) -> Self:  # type: ignore[override]
        """Preserve diagnostic metadata when Python splits this group.

        :param exceptions: Members selected by subgroup or split operations.
        :returns: Same concrete group type with the selected members and original code.
        """
        result = type(self)(self.message, exceptions, code=self.code)
        self.copy_diagnostic_fields(result)
        copy_failure_state(self, result)
        return result

    def __copy__(self) -> Self:
        """Copy a group without reconstructing its native members.

        :returns: Independent diagnostic state containing the same member objects.
        """
        return self.derive(self.exceptions)

    def __str__(self) -> str:
        """Render the combined diagnostic followed by each preserved failure.

        :returns: Multiline error scene with ordered member diagnostics.
        """
        from lclang.error.diagnostic_rendering import render_error

        return render_error(self)
