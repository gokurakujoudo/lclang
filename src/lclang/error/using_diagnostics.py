"""Aliases for an actual generated using target scope.

Defines ``UsingDiagnosticContext``, ``ACTIVE_USING_DIAGNOSTICS``,
``scope_using_diagnostics``, ``describe_using_subject``.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lclang.lang.common.source_location import SourceSpan


@dataclass(frozen=True, slots=True)
class UsingDiagnosticContext:
    """Identify generated names through the actual using operation.

    :param target_name: Actual generated binding name.
    :param target_frame: Actual disposable target Frame identifier.
    :param context_frame: Actual chronological definitions Frame identifier.
    :param span: Original declaration's frozen source range.
    """

    target_name: str
    target_frame: str
    context_frame: str
    span: SourceSpan


# The unitless None default leaves ordinary user bindings and Frames unchanged.
ACTIVE_USING_DIAGNOSTICS: ContextVar[UsingDiagnosticContext | None] = ContextVar(
    "lclang_using_diagnostics", default=None
)


@contextmanager
def scope_using_diagnostics(context: UsingDiagnosticContext) -> Generator[None]:
    """Alias generated names while retaining raw record context.

    :param context: Source and generated identifiers already obtained by the loader.
    :returns: Scope restoring the previous operation after every exit.
    """
    token = ACTIVE_USING_DIAGNOSTICS.set(context)
    try:
        yield
    finally:
        ACTIVE_USING_DIAGNOSTICS.reset(token)


def describe_using_subject(name: str) -> str:
    """Translate only the active generated target binding.

    :param name: Actual runtime subject.
    :returns: Human target label or the unchanged user subject.
    """
    context = ACTIVE_USING_DIAGNOSTICS.get()
    return "using target" if context is not None and name == context.target_name else name
