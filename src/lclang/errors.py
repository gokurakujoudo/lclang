"""Structured public exception hierarchy for lclang."""

from __future__ import annotations

from lclang.source import SourceSpan


class LclError(Exception):
    """Base class for expected language and runtime failures.

    :param message: Non-empty human-readable failure description.
    :param span: Optional source range responsible for the failure.
    :param code: Optional stable machine-readable override.
    :param variable_stack: Ordered definition owners active at failure time.
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
    ) -> None:
        """Create a structured error.

        :param message: Non-empty human-readable failure description.
        :param span: Optional source range responsible for the failure.
        :param code: Optional stable machine-readable override.
        :param variable_stack: Ordered definition owners active at failure time.
        :raises TypeError: If *variable_stack* is not a tuple of strings.
        :raises ValueError: If the message, code, or a variable name is empty.
        """
        selected_code = self.default_code if code is None else code
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
        """Render a stable single-line diagnostic.

        :returns: Code, message, and optional source coordinates.
        """
        stack = ""
        if self.variable_stack:
            path = " -> ".join(self.variable_stack)
            stack = f" [variable evaluation stack: {path}]"
        diagnostic = f"[{self.code}] {self.message}{stack}"
        if self.span is None:
            return diagnostic
        start = self.span.start
        return f"{self.span.origin.name}:{start.line}:{start.column}: {diagnostic}"


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
