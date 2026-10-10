"""Structured public exception hierarchy for lclang."""

from __future__ import annotations

from copy import copy
from typing import Self

from lclang.diagnostics import ACTIVE_MASKED_VALUE
from lclang.error_context import ConfigLoadFrame, EvaluationContextFrame, validate_record_tuple
from lclang.error_rendering import render_error
from lclang.source import SourceSpan
from lclang.utils.representation import safe_repr


class LclError(Exception):
    """Base class for expected language and runtime failures.

    :param message: Non-empty human-readable failure description.
    :param span: Optional source range responsible for the failure.
    :param code: Optional stable machine-readable override.
    :param variable_stack: Ordered definition owners active at failure time.
    :param config_stack: Immutable file-introduction frames, outermost first.
    :param evaluation_context: Detached active expression and used-value snapshots.
    :raises TypeError: If *variable_stack* is not a tuple of strings.
    :raises ValueError: If the message, code, or a variable name is empty.

    .. note::
       String conversion is stable and includes source coordinates when present.
    """

    default_code = "LCL0001"

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
        :raises TypeError: If *variable_stack* is not a tuple of strings.
        :raises ValueError: If the message, code, or a variable name is empty.
        """
        selected_code = self.default_code if code is None else code
        if not isinstance(message, str) or not isinstance(selected_code, str):
            raise TypeError("LCL error message and code must be strings")
        if span is not None and not isinstance(span, SourceSpan):
            raise TypeError("LCL error span must be a SourceSpan or None")
        validate_record_tuple(config_stack, ConfigLoadFrame, "config stack")
        validate_record_tuple(evaluation_context, EvaluationContextFrame, "evaluation context")
        if not message:
            raise ValueError("LCL error message cannot be empty")
        if not selected_code:
            raise ValueError("LCL error code cannot be empty")
        if not isinstance(variable_stack, tuple) or any(
            not isinstance(name, str) for name in variable_stack
        ):
            raise TypeError("variable evaluation stack must be a tuple of strings")
        if any(not name for name in variable_stack):
            raise ValueError("variable evaluation stack names cannot be empty")
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
        self.native_cause = (
            f"{type(cause).__name__}: {safe_repr(cause, renderer=str, max_length=None)}"
        )

    def attach_evaluation_context(self, context: tuple[EvaluationContextFrame, ...]) -> None:
        """Retain the first detached failure snapshot during propagation.

        :param context: Complete active evaluation path and protected read values.
        :raises TypeError: If context is not a tuple of evaluation records.
        """
        validate_record_tuple(context, EvaluationContextFrame, "evaluation context")
        if not self.evaluation_context:
            self.evaluation_context = context

    def derive_config_context(self, frame: ConfigLoadFrame) -> Self:
        """Copy a failure before adding a caller-specific file-introduction frame.

        :param frame: Outer source-level load placement to prepend.
        :returns: Same concrete error type with the original code, cause, and traceback.
        :raises TypeError: If frame is not a ConfigLoadFrame.
        """
        if not isinstance(frame, ConfigLoadFrame):
            raise TypeError("config load frame must be a ConfigLoadFrame")
        result = copy(self)
        result.config_stack = (frame, *self.config_stack)
        result.__cause__ = self.__cause__
        result.__context__ = self.__context__
        result.__suppress_context__ = self.__suppress_context__
        result.__traceback__ = self.__traceback__
        if hasattr(self, "__notes__"):
            result.__notes__ = list(self.__notes__)
        return result

    def attach_variable_stack(self, variable_stack: tuple[str, ...]) -> None:
        """Attach the first non-empty variable evaluation path.

        :param variable_stack: Ordered definition owners active at failure time.
        :returns: ``None`` after retaining a previously absent stack.
        :raises TypeError: If *variable_stack* is not a tuple of strings.
        :raises ValueError: If a variable name is empty.

        .. note::
           A deeper stack already attached during propagation is never replaced.
        """
        if not isinstance(variable_stack, tuple) or any(
            not isinstance(name, str) for name in variable_stack
        ):
            raise TypeError("variable evaluation stack must be a tuple of strings")
        if any(not name for name in variable_stack):
            raise ValueError("variable evaluation stack names cannot be empty")
        if self.variable_stack or not variable_stack:
            return
        self.variable_stack = variable_stack

    def __str__(self) -> str:
        """Render a detached multiline diagnostic without further evaluation.

        :returns: Action, code, complete context, and original failure reason.
        """
        return render_error(self)


class LclSyntaxError(LclError):
    """Report invalid LCL source syntax.

    .. note::
       The default diagnostic code is ``LCL1001``.
    """

    default_code = "LCL1001"


class LclNameError(LclError):
    """Report an unresolved LCL variable.

    .. note::
       The default diagnostic code is ``LCL2001``.
    """

    default_code = "LCL2001"


class LclEvaluationError(LclError):
    """Report a failure while evaluating an LCL expression.

    .. note::
       The default diagnostic code is ``LCL3001``.
    """

    default_code = "LCL3001"


class LclCircularDependencyError(LclEvaluationError):
    """Report a circular variable or function dependency.

    .. note::
       The default diagnostic code is ``LCL3002``.
    """

    default_code = "LCL3002"


class LclClosedFrameError(LclEvaluationError):
    """Report evaluation attempted through a closed Frame.

    .. note::
       The default diagnostic code is ``LCL3003``.
    """

    default_code = "LCL3003"


class LclConfigError(LclError):
    """Report invalid configuration content or loading.

    .. note::
       The default diagnostic code is ``LCL4001``.
    """

    default_code = "LCL4001"


class LclCliError(LclError):
    """Base class for command-line framework failures.

    .. note::
       The default diagnostic code is ``LCL5001``.
    """

    default_code = "LCL5001"


class LclCliUsageError(LclCliError):
    """Report invalid command-line usage.

    .. note::
       The default diagnostic code is ``LCL5002``.
    """

    default_code = "LCL5002"
