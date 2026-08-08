"""Task-local definition ownership for fundamental LCL functions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pylcl.errors import LclEvaluationError

# Active Frame definition name, absent outside definition evaluation.
ACTIVE_DEFINITION: ContextVar[str | None] = ContextVar(
    "pylcl_active_definition",
    default=None,
)


@contextmanager
def definition_scope(name: str) -> Iterator[None]:
    """Select one definition name for the duration of its evaluation.

    :param name: Non-empty definition name owned by the active Frame.
    :returns: Context manager iterator restoring the previous task-local name.
    :raises ValueError: If *name* is empty.

    .. note::
       Nested definitions temporarily replace their dependant and restore it.
    """
    if not name:
        raise ValueError("definition name cannot be empty")
    token = ACTIVE_DEFINITION.set(name)
    try:
        yield
    finally:
        ACTIVE_DEFINITION.reset(token)


def lhs() -> str:
    """Return the name of the Frame definition currently being evaluated.

    :returns: Active definition name as a plain string.
    :raises LclEvaluationError: If no Frame definition evaluation is active.

    .. note::
       Direct expression evaluation has no left-hand definition context.
    """
    name = ACTIVE_DEFINITION.get()
    if name is None:
        message = "lhs() is only available while evaluating a Frame definition"
        raise LclEvaluationError(message)
    return name


def active_definition() -> str | None:
    """Return the optional definition owner active in this task.

    :returns: Active Frame definition name, or ``None`` outside a definition.

    .. note::
       Function values capture this name to preserve lexical ``lhs()`` meaning.
    """
    return ACTIVE_DEFINITION.get()
