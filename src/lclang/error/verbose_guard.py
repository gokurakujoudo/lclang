"""Isolate optional verbose work without swallowing native control signals.

Defines ``VerboseFailureScope``, ``guard_verbose_operation``, ``ignore_verbose_failure``.
"""

from collections.abc import Callable
from contextlib import ContextDecorator
from dataclasses import dataclass
from types import TracebackType

from lclang.error.native_wrap import is_ordinary_failure


def guard_verbose_operation[**Params, Result](
    operation: Callable[Params, Result],
) -> Callable[Params, Result | None]:
    """Discard ordinary failures from one optional diagnostic producer.

    :param operation: Diagnostic-only function, never business execution.
    :returns: Signature-preserving producer returning None after an ordinary failure.
    """
    return ignore_verbose_failure()(operation)


@dataclass(frozen=True, slots=True)
class VerboseFailureScope(ContextDecorator):
    """Discard optional diagnostic errors while retaining required output failures.

    :param required: Whether diagnostic output was explicitly requested.
    """

    required: bool = False

    def __enter__(self) -> None:
        """Enter one diagnostic phase without acquiring execution resources."""

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """Discard only an ordinary exception from optional diagnostic work.

        :param error_type: Exception type, or None after successful diagnostic work.
        :param error: Actual diagnostic failure, or None after success.
        :param traceback: Original failure traceback, preserved when propagating.
        :returns: Whether the optional diagnostic error is suppressed.
        """
        return error is not None and not self.required and is_ordinary_failure(error)


def ignore_verbose_failure(*, required: bool = False) -> VerboseFailureScope:
    """Isolate a diagnostic phase without surrounding the business operation.

    :param required: Whether an explicit display consumer requires this diagnostic work.
    :returns: Scope discarding ordinary failures only from optional diagnostic work.
    """
    return VerboseFailureScope(required)
