"""Structured public exception hierarchy for pylcl."""

from __future__ import annotations

from pylcl.source import SourceSpan


class LclError(Exception):
    """Base class for expected language and runtime failures.

    :param message: Non-empty human-readable failure description.
    :param span: Optional source range responsible for the failure.
    :param code: Optional stable machine-readable override.
    :raises ValueError: If *message* or the selected code is empty.

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
    ) -> None:
        """Create a structured error.

        :param message: Non-empty human-readable failure description.
        :param span: Optional source range responsible for the failure.
        :param code: Optional stable machine-readable override.
        :raises ValueError: If the message or selected code is empty.
        """
        selected_code = self.default_code if code is None else code
        if not message:
            raise ValueError("LCL error message cannot be empty")
        if not selected_code:
            raise ValueError("LCL error code cannot be empty")
        super().__init__(message)
        self.message = message
        self.span = span
        self.code = selected_code

    def __str__(self) -> str:
        """Render a stable single-line diagnostic.

        :returns: Code, message, and optional source coordinates.
        """
        diagnostic = f"[{self.code}] {self.message}"
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
