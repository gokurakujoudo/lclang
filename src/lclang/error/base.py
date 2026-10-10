"""Dependency-light exception root and API validation failures."""

from __future__ import annotations

from copy import copy
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, Any, Self

from lclang.error.codes.general import Code as general_codes
from lclang.error.masking import ACTIVE_MASKED_VALUE

if TYPE_CHECKING:
    from lclang.error.context import ConfigLoadFrame, EvaluationContextFrame
    from lclang.source import SourceSpan


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
                general_codes.CONSTRUCTOR_CALL if signature else general_codes.CONSTRUCTOR_OPERATION
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
    :raises LclValidationError: If *variable_stack* is not a tuple of strings.
    :raises LclValidationError: If the message, code, or a variable name is empty.

    .. note::
       String conversion is stable and includes source coordinates when present.
    """

    default_code = str(general_codes.BASE)

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
        from lclang.error.context import (
            ConfigLoadFrame,
            EvaluationContextFrame,
            validate_record_tuple,
        )
        from lclang.source import SourceSpan

        selected_code = self.default_code if code is None else code
        if not isinstance(message, str) or not isinstance(selected_code, str):
            raise LclValidationError(
                "LCL error message and code must be strings", code=general_codes.MESSAGE_TYPE
            )
        if span is not None and not isinstance(span, SourceSpan):
            raise LclValidationError(
                "LCL error span must be a SourceSpan or None", code=general_codes.SPAN_TYPE
            )
        validate_record_tuple(config_stack, ConfigLoadFrame, "config stack")
        validate_record_tuple(evaluation_context, EvaluationContextFrame, "evaluation context")
        if not message:
            raise LclValidationError(
                "LCL error message cannot be empty", code=general_codes.MESSAGE_EMPTY
            )
        if not selected_code:
            raise LclValidationError(
                "LCL error code cannot be empty", code=general_codes.MESSAGE_EMPTY
            )
        if not isinstance(variable_stack, tuple) or any(
            not isinstance(name, str) for name in variable_stack
        ):
            raise LclValidationError(
                "variable evaluation stack must be a tuple of strings",
                code=general_codes.STACK_TYPE,
            )
        if any(not name for name in variable_stack):
            raise LclValidationError(
                "variable evaluation stack names cannot be empty",
                code=general_codes.MESSAGE_EMPTY,
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

    def freeze_native_cause(self, cause: BaseException) -> None:
        """Retain the original native failure description without changing its object.

        :param cause: Native exception preserved separately through ``__cause__``.
        """
        from lclang.utils.representation import safe_repr

        self.native_cause = (
            f"{type(cause).__name__}: {safe_repr(cause, renderer=str, max_length=None)}"
        )

    def attach_evaluation_context(self, context: tuple[EvaluationContextFrame, ...]) -> None:
        """Retain the first detached failure snapshot during propagation.

        :param context: Complete active evaluation path and protected read values.
        :raises LclValidationError: If context is not a tuple of evaluation records.
        """
        from lclang.error.context import EvaluationContextFrame, validate_record_tuple

        validate_record_tuple(context, EvaluationContextFrame, "evaluation context")
        if not self.evaluation_context:
            self.evaluation_context = context

    def derive_config_context(self, frame: ConfigLoadFrame) -> Self:
        """Copy a failure before adding a caller-specific file-introduction frame.

        :param frame: Outer source-level load placement to prepend.
        :returns: Same concrete error type with the original code, cause, and traceback.
        :raises LclValidationError: If frame is not a ConfigLoadFrame.
        """
        from lclang.error.context import ConfigLoadFrame

        if not isinstance(frame, ConfigLoadFrame):
            raise LclValidationError(
                "config load frame must be a ConfigLoadFrame", code=general_codes.LOAD_FRAME_TYPE
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
                code=general_codes.STACK_TYPE,
            )
        if any(not name for name in variable_stack):
            raise LclValidationError(
                "variable evaluation stack names cannot be empty",
                code=general_codes.MESSAGE_EMPTY,
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
        vars(result).update(vars(self))
        copy_failure_state(self, result)
        return result

    def __str__(self) -> str:
        """Render a detached multiline diagnostic without further evaluation.

        :returns: Action, code, complete context, and original failure reason.
        """
        from lclang.error.rendering import render_error

        return render_error(self)


class LclValidationError(LclError):
    """Report invalid arguments or inconsistent public values."""

    default_code = str(general_codes.VALIDATION)


class LclStateError(LclError):
    """Report an operation unavailable in the current state."""

    default_code = str(general_codes.STATE)


class LclAttributeError(LclError, AttributeError):
    """Retain the Python missing-attribute protocol with a diagnostic code."""

    default_code = str(general_codes.ATTRIBUTE)


class LclFrozenAttributeError(LclAttributeError, FrozenInstanceError):
    """Retain frozen dataclass attribute semantics in a structured diagnostic."""

    default_code = str(general_codes.FROZEN_ATTRIBUTE)


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
