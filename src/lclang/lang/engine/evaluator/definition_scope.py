"""Task-local definition ownership for fundamental LCL functions.

Defines ``definition_scope``, ``lhs``, ``active_definition``, ``active_definition_stack``.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from lclang.error import LanguageErrorCode, LclEvaluationError
from lclang.error.operation_guard import guard_failure

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
    :raises LclEvaluationError: If *name* is empty.

    .. note::
       Nested definitions temporarily replace their dependant and restore it.
    """
    if not name:
        raise LclEvaluationError(
            "definition name cannot be empty",
            code=LanguageErrorCode.E33_DEFINITION_NAME_CANNOT_BE_EMPTY,
        )
    stack = ACTIVE_DEFINITION_STACK.get()
    selected = stack if stack[-1:] == (name,) else (*stack, name)
    token = ACTIVE_DEFINITION_STACK.set(selected)
    try:
        yield
    finally:
        ACTIVE_DEFINITION_STACK.reset(token)


@guard_failure(LclEvaluationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
def lhs() -> str:
    """Return the name of the Frame definition currently being evaluated.

    :returns: Active definition name as a plain string.
    :raises LclEvaluationError: If no Frame definition evaluation is active.

    .. note::
       Unnamed Frame expressions use ``<expr>`` as their lexical owner.
    """
    stack = ACTIVE_DEFINITION_STACK.get()
    if not stack:
        message = "lhs() is only available while evaluating a Frame definition"
        raise LclEvaluationError(message, code=LanguageErrorCode.E33_LHS_FAILURE)
    return stack[-1]


@guard_failure(LclEvaluationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
def active_definition() -> str | None:
    """Return the optional definition owner active in this task.

    :returns: Active Frame definition name, or ``None`` outside a definition.

    .. note::
       Function values capture this name to preserve lexical ``lhs()`` meaning.
    """
    stack = ACTIVE_DEFINITION_STACK.get()
    return stack[-1] if stack else None


@guard_failure(LclEvaluationError, LanguageErrorCode.E33_NAME_RESOLUTION_NATIVE_FAILURE)
def active_definition_stack() -> tuple[str, ...]:
    """Return the ordered variable owners active in this task.

    :returns: Immutable direct-to-innermost definition owner path.

    .. note::
       Adjacent calls owned by the same lexical definition occupy one entry.
    """
    return ACTIVE_DEFINITION_STACK.get()
