"""Dependency-light exception root and API validation failures.

Defines ``ErrorType``, ``LclError``, ``LclValidationError``, ``LclStateError``,
``LclAttributeError``, ``LclFrozenAttributeError``, ``copy_failure_state``.
"""

from __future__ import annotations

from copy import copy
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, Any, Self

from lclang.error.codes.e0_general_error_code import GeneralErrorCode
from lclang.error.mask_scope import ACTIVE_MASKED_VALUE

if TYPE_CHECKING:
    from lclang.common.source_location import SourceSpan
    from lclang.error.diagnostic_records import ConfigLoadFrame, EvaluationContextFrame


class ErrorType(type):
    """Guard exception constructor calls without importing diagnostic adapters."""

    def __call__(self, *args: object, **kwargs: object) -> Any:
        """Construct a diagnostic or safely classify a malformed constructor call.

        :param args: Positional constructor arguments.
        :param kwargs: Named constructor arguments.
        :returns: Valid instance of the requested exception class.
        :raises LclValidationError: If constructor arguments or native construction fail.
        """
        try:
            # A metaclass must retain each subclass's constructor result type.
            return super().__call__(*args, **kwargs)
        except LclError:
            raise
        except Exception as error:
            if isinstance(error, (StopIteration, StopAsyncIteration)):
                raise
            trace = error.__traceback__
            signature = isinstance(error, TypeError) and trace is not None and trace.tb_next is None
            code = (
                GeneralErrorCode.E11_CONSTRUCTOR_CALL
                if signature
                else GeneralErrorCode.E11_CONSTRUCTOR_OPERATION
            )
            raise LclValidationError(
                "invalid exception constructor arguments", code=code
            ) from error


class LclError(Exception, metaclass=ErrorType):
    """Base class for expected language and runtime failures.

    :param message: Non-empty human-readable failure description.
    :param span: Optional source range responsible for the failure.
    :param code: Optional stable machine-readable override.
    :param variable_stack: Ordered definition owners active at failure time.
    :param config_stack: Immutable file-introduction frames, outermost first.
    :param evaluation_context: Detached active expression and used-value snapshots.
    :ivar binding_names: Conflicting declaration names, or an empty tuple.
    :raises LclValidationError: If *variable_stack* is not a tuple of strings.
    :raises LclValidationError: If the message, code, or a variable name is empty.

    .. note::
       String conversion is stable and includes source coordinates when present.
    """

    default_code = str(GeneralErrorCode.E00_UNCLASSIFIED_FAILURE)

    def __init__(
        self,
        message: str,
        *,
        span: SourceSpan | None = None,
        code: str | None = None,
        variable_stack: tuple[str, ...] = (),
        config_stack: tuple[ConfigLoadFrame, ...] = (),
        evaluation_context: tuple[EvaluationContextFrame, ...] = (),
    ) -> None:
        """Create a structured error.

        :param message: Non-empty human-readable failure description.
        :param span: Optional source range responsible for the failure.
        :param code: Optional stable machine-readable override.
        :param variable_stack: Ordered definition owners active at failure time.
        :param config_stack: Immutable file-introduction frames, outermost first.
        :param evaluation_context: Detached active expression and used-value snapshots.
        :raises LclValidationError: If *variable_stack* is not a tuple of strings.
        :raises LclValidationError: If the message, code, or a variable name is empty.
        """
        from lclang.common.source_location import SourceSpan
        from lclang.error.diagnostic_records import (
            ConfigLoadFrame,
            EvaluationContextFrame,
            validate_record_tuple,
        )

        selected_code = self.default_code if code is None else code
        if not isinstance(message, str) or not isinstance(selected_code, str):
            raise LclValidationError(
                "LCL error message and code must be strings", code=GeneralErrorCode.E11_MESSAGE_TYPE
            )
        if span is not None and not isinstance(span, SourceSpan):
            raise LclValidationError(
                "LCL error span must be a SourceSpan or None", code=GeneralErrorCode.E11_SPAN_TYPE
            )
        validate_record_tuple(config_stack, ConfigLoadFrame, "config stack")
        validate_record_tuple(evaluation_context, EvaluationContextFrame, "evaluation context")
        if not message:
            raise LclValidationError(
                "LCL error message cannot be empty", code=GeneralErrorCode.E11_MESSAGE_EMPTY
            )
        if not selected_code:
            raise LclValidationError(
                "LCL error code cannot be empty", code=GeneralErrorCode.E11_MESSAGE_EMPTY
            )
        if not isinstance(variable_stack, tuple) or any(
            not isinstance(name, str) for name in variable_stack
        ):
            raise LclValidationError(
                "variable evaluation stack must be a tuple of strings",
                code=GeneralErrorCode.E11_STACK_TYPE,
            )
        if any(not name for name in variable_stack):
            raise LclValidationError(
                "variable evaluation stack names cannot be empty",
                code=GeneralErrorCode.E11_MESSAGE_EMPTY,
            )
        super().__init__(message)
        self.message = message
        self.span = span
        self.code = selected_code
        self.variable_stack = variable_stack
        self.config_stack = config_stack
        self.evaluation_context = evaluation_context
        self.masked = ACTIVE_MASKED_VALUE.get()
        self.native_cause: str | None = None
        self.binding_names: tuple[str, ...] = ()

    def freeze_native_cause(self, cause: BaseException) -> None:
        """Retain the original native failure description without changing its object.

        :param cause: Native exception preserved separately through ``__cause__``.
        """
        from lclang.utils.value_representation import safe_repr

        self.native_cause = (
            f"{type(cause).__name__}: {safe_repr(cause, renderer=str, max_length=None)}"
        )

    def attach_evaluation_context(self, context: tuple[EvaluationContextFrame, ...]) -> None:
        """Retain the first detached failure snapshot during propagation.

        :param context: Complete active evaluation path and protected read values.
        :raises LclValidationError: If context is not a tuple of evaluation records.
        """
        from lclang.error.diagnostic_records import EvaluationContextFrame, validate_record_tuple

        validate_record_tuple(context, EvaluationContextFrame, "evaluation context")
        if not self.evaluation_context:
            self.evaluation_context = context

    def derive_config_context(self, frame: ConfigLoadFrame) -> Self:
        """Copy a failure before adding a caller-specific file-introduction frame.

        :param frame: Outer source-level load placement to prepend.
        :returns: Same concrete error type with the original code, cause, and traceback.
        :raises LclValidationError: If frame is not a ConfigLoadFrame.
        """
        from lclang.error.diagnostic_records import ConfigLoadFrame

        if not isinstance(frame, ConfigLoadFrame):
            raise LclValidationError(
                "config load frame must be a ConfigLoadFrame",
                code=GeneralErrorCode.E11_LOAD_FRAME_TYPE,
            )
        result = copy(self)
        result.config_stack = (frame, *self.config_stack)
        return result

    def attach_variable_stack(self, variable_stack: tuple[str, ...]) -> None:
        """Attach the first non-empty variable evaluation path.

        :param variable_stack: Ordered definition owners active at failure time.
        :returns: ``None`` after retaining a previously absent stack.
        :raises LclValidationError: If *variable_stack* is not a tuple of strings.
        :raises LclValidationError: If a variable name is empty.

        .. note::
           A deeper stack already attached during propagation is never replaced.
        """
        if not isinstance(variable_stack, tuple) or any(
            not isinstance(name, str) for name in variable_stack
        ):
            raise LclValidationError(
                "variable evaluation stack must be a tuple of strings",
                code=GeneralErrorCode.E11_STACK_TYPE,
            )
        if any(not name for name in variable_stack):
            raise LclValidationError(
                "variable evaluation stack names cannot be empty",
                code=GeneralErrorCode.E11_MESSAGE_EMPTY,
            )
        if self.variable_stack or not variable_stack:
            return
        self.variable_stack = variable_stack

    def __copy__(self) -> Self:
        """Copy diagnostic state without invoking a specialized constructor.

        :returns: Same error type with independent fields and original arguments.
        """
        result = Exception.__new__(type(self))
        result.args = self.args
        self.copy_diagnostic_fields(result)
        copy_failure_state(self, result)
        return result

    def copy_diagnostic_fields(self, target: LclError) -> None:
        """Copy declared fields into a compatible allocated diagnostic.

        :param target: Same concrete error type or a subtype, already allocated.
        :raises LclValidationError: If the target has an incompatible error type.

        .. note::
           Subclasses extend this hook for their fields. Group messages and
           selected member arguments are retained by the native group allocator.
        """
        if not isinstance(target, type(self)):
            raise LclValidationError(
                "diagnostic copy target must have a compatible LCL error type",
                code=GeneralErrorCode.E11_COPY_TARGET_TYPE,
            )
        if not isinstance(target, ExceptionGroup):
            target.message = self.message
        target.span = self.span
        target.code = self.code
        target.variable_stack = self.variable_stack
        target.config_stack = self.config_stack
        target.evaluation_context = self.evaluation_context
        target.masked = self.masked
        target.native_cause = self.native_cause
        target.binding_names = self.binding_names

    def __str__(self) -> str:
        """Render a detached multiline diagnostic without further evaluation.

        :returns: Action, code, complete context, and original failure reason.
        """
        from lclang.error.diagnostic_rendering import render_error

        return render_error(self)


class LclValidationError(LclError):
    """Report invalid arguments or inconsistent public values.

    :ivar binding_names: Unitless conflicting names in detection order; empty
       when the validation failure does not describe a binding conflict.
    """

    default_code = str(GeneralErrorCode.E11_VALIDATION)


class LclStateError(LclError):
    """Report an operation unavailable in the current state."""

    default_code = str(GeneralErrorCode.E12_STATE)


class LclAttributeError(LclError, AttributeError):
    """Retain the Python missing-attribute protocol with a diagnostic code."""

    default_code = str(GeneralErrorCode.E13_ATTRIBUTE)


class LclFrozenAttributeError(LclAttributeError, FrozenInstanceError):
    """Retain frozen dataclass attribute semantics in a structured diagnostic."""

    default_code = str(GeneralErrorCode.E13_FROZEN_ATTRIBUTE)


def copy_failure_state(source: BaseException, target: BaseException) -> None:
    """Copy Python propagation state while keeping diagnostic notes independent.

    :param source: Failure whose causes, traceback and notes are retained.
    :param target: Detached failure receiving that propagation state.
    """
    target.__cause__ = source.__cause__
    target.__context__ = source.__context__
    target.__suppress_context__ = source.__suppress_context__
    target.__traceback__ = source.__traceback__
    if hasattr(source, "__notes__"):
        target.__notes__ = list(source.__notes__)
