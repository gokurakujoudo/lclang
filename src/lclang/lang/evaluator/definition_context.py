"""Task-local definition ownership for fundamental LCL functions."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from lclang.errors import LclEvaluationError

# Active ordered Frame and lexical-function definition owners.
# Unitless context key names identify task-local lexical definition state. An empty initial
# stack denotes no active definition; nested entries preserve lhs() ownership independently
# across tasks.
ACTIVE_DEFINITION_STACK: ContextVar[tuple[str, ...]] = ContextVar(
    "lclang_active_definition_stack",
    default=(),
)


@contextmanager
def definition_scope(name: str) -> Generator[None]:
    """Select one definition name for the duration of its evaluation.

    :param name: Non-empty definition name owned by the active Frame.
    :returns: Context manager iterator restoring the previous task-local name.
    :raises ValueError: If *name* is empty.

    .. note::
       Nested definitions temporarily replace their dependant and restore it.
    """
    if not name:
        raise ValueError("definition name cannot be empty")
    stack = ACTIVE_DEFINITION_STACK.get()
    selected = stack if stack[-1:] == (name,) else (*stack, name)
    token = ACTIVE_DEFINITION_STACK.set(selected)
    try:
        yield
    finally:
        ACTIVE_DEFINITION_STACK.reset(token)


def lhs() -> str:
    """Return the name of the Frame definition currently being evaluated.

    :returns: Active definition name as a plain string.
    :raises LclEvaluationError: If no Frame definition evaluation is active.

    .. note::
       Direct expression evaluation has no left-hand definition context.
    """
    stack = ACTIVE_DEFINITION_STACK.get()
    if not stack:
        message = "lhs() is only available while evaluating a Frame definition"
        raise LclEvaluationError(message)
    return stack[-1]


def active_definition() -> str | None:
    """Return the optional definition owner active in this task.

    :returns: Active Frame definition name, or ``None`` outside a definition.

    .. note::
       Function values capture this name to preserve lexical ``lhs()`` meaning.
    """
    stack = ACTIVE_DEFINITION_STACK.get()
    return stack[-1] if stack else None


def active_definition_stack() -> tuple[str, ...]:
    """Return the ordered variable owners active in this task.

    :returns: Immutable direct-to-innermost definition owner path.

    .. note::
       Adjacent calls owned by the same lexical definition occupy one entry.
    """
    return ACTIVE_DEFINITION_STACK.get()
