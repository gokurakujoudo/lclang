"""Structured ordinary failure groups with Python splitting semantics.

Defines ``LclErrorGroup`` and ``validate_group_members``.
"""

from collections.abc import Sequence
from typing import Self, cast, overload

from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.exception_base import LclError, LclValidationError, copy_failure_state
from lclang.error.native_wrap import is_ordinary_failure, wrap_failure


class LclErrorGroup(ExceptionGroup, LclError):
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
        exceptions: Sequence[BaseException],
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
        members: list[LclError] = []
        for error in validate_group_members(exceptions):
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
        exceptions: Sequence[BaseException],
        *,
        code: str = GeneralErrorCode.E21_GROUP,
    ) -> None:
        """Keep the state validated and installed during allocation.

        :param message: Combined description already stored by allocation.
        :param exceptions: Original member sequence already validated.
        :param code: Diagnostic identifier already installed.
        """

    @overload
    def derive[E: Exception](self, exceptions: Sequence[E], /) -> ExceptionGroup[E]:  # noqa: D418
        """Preserve the native ordinary-member typing contract.

        :param exceptions: Selected ordinary exception members.
        :returns: Same concrete group retaining the selected member types.
        """
        ...

    @overload
    def derive[E: BaseException](  # noqa: D418
        self, exceptions: Sequence[E], /
    ) -> BaseExceptionGroup[E]:
        """Accept the native base-group signature while validating ordinary members.

        :param exceptions: Selected members supplied through the base-group interface.
        :returns: Same concrete group when every member is an ordinary failure.
        :raises LclValidationError: If any member is a control signal.
        """
        ...

    def derive(self, exceptions: Sequence[BaseException], /) -> BaseExceptionGroup[BaseException]:
        """Preserve diagnostic metadata when Python splits this group.

        :param exceptions: Members selected by subgroup or split operations.
        :returns: Same concrete group type with the selected members and original code.
        """
        result = ExceptionGroup.__new__(
            type(self), self.message, validate_group_members(exceptions)
        )
        self.copy_diagnostic_fields(result)
        copy_failure_state(self, result)
        return result

    def __copy__(self) -> Self:
        """Copy a group without reconstructing its native members.

        :returns: Independent diagnostic state containing the same member objects.
        """
        return cast(Self, self.derive(self.exceptions))

    def __str__(self) -> str:
        """Render the combined diagnostic followed by each preserved failure.

        :returns: Multiline error scene with ordered member diagnostics.
        """
        from lclang.error.diagnostic_rendering import render_error

        return render_error(self)


def validate_group_members(exceptions: Sequence[BaseException]) -> Sequence[Exception]:
    """Require ordinary members before allocating or deriving an LCL group.

    :param exceptions: Nonempty member sequence supplied by an application or Python.
    :returns: Validated sequence with cancellation and iterator controls excluded.
    :raises LclValidationError: If the sequence is empty or contains a control signal.
    """
    if (
        not isinstance(exceptions, Sequence)
        or not exceptions
        or any(not is_ordinary_failure(error) for error in exceptions)
    ):
        raise LclValidationError(
            "error group requires a nonempty sequence of ordinary exceptions",
            code=GeneralErrorCode.E21_GROUP_CONTENT,
        )
    return cast(Sequence[Exception], exceptions)
