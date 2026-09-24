"""Context-local hooks for optional runtime evaluation budgets."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Protocol

from lclang.source import SourceSpan


class InternalEvaluationGuard(Protocol):
    """Observe evaluator work that is subject to runtime budgets.

    .. note::
       Implementations own the actual limit checks; this protocol only defines
       the callbacks used by the evaluator context.
    """

    def enter(self, span: SourceSpan, depth: int) -> None:
        """Record entry into one AST node.

        :param span: Source range belonging to the node being entered.
        :param depth: One-based evaluator depth after entering the node.
        :returns: ``None``.

        .. note::
           A guard may raise its configured limit exception before evaluation
           of the node continues.
        """
        ...

    def collection(self, size: int, span: SourceSpan) -> None:
        """Record materialization of a collection.

        :param size: Number of elements about to be materialized.
        :param span: Source range responsible for the collection operation.
        :returns: ``None``.

        .. note::
           The callback receives the requested size before the collection is
           constructed, allowing a guard to reject oversized materialization.
        """
        ...


# Task-local evaluation state starts unset or at zero levels; these defaults identify a root
# evaluation and share its budget across nested calls.
_ACTIVE_GUARD: ContextVar[InternalEvaluationGuard | None] = ContextVar(
    "lclang_evaluation_guard",
    default=None,
)
# Task-local evaluation state starts unset or at zero levels; these defaults identify a root
# evaluation and share its budget across nested calls.
_EVALUATION_DEPTH: ContextVar[int] = ContextVar("lclang_evaluation_depth", default=0)


def internal_has_guard() -> bool:
    """Report whether the current context has an installed budget guard.

    :returns: ``True`` when evaluation callbacks are active, otherwise
       ``False``.

    .. note::
       The result is context-local, so concurrent tasks do not observe one
       another's guard installation.
    """
    return _ACTIVE_GUARD.get() is not None


@contextmanager
def internal_install_guard(guard: InternalEvaluationGuard) -> Generator[None]:
    """Install a guard for the dynamic extent of a context manager.

    :param guard: Callback object receiving node and collection events.
    :returns: A context-manager iterator yielding ``None``.

    .. note::
       The previous context-local guard is restored even when the managed
       evaluation raises or is cancelled.
    """
    token = _ACTIVE_GUARD.set(guard)
    try:
        yield
    finally:
        _ACTIVE_GUARD.reset(token)


def internal_enter_node(span: SourceSpan) -> Token[int] | None:
    """Notify the active guard of node entry and advance evaluation depth.

    :param span: Source range belonging to the node being entered.
    :returns: A depth-reset token, or ``None`` when no guard is active.

    .. note::
       If the guard rejects entry, the depth context is restored before the
       exception propagates to the evaluator.
    """
    guard = _ACTIVE_GUARD.get()
    if guard is None:
        return None
    depth = _EVALUATION_DEPTH.get() + 1
    token = _EVALUATION_DEPTH.set(depth)
    try:
        guard.enter(span, depth)
    except BaseException:
        _EVALUATION_DEPTH.reset(token)
        raise
    return token


def internal_leave_node(token: Token[int] | None) -> None:
    """Restore the depth context captured when a node was entered.

    :param token: Token returned by :func:`_enter_node`, or ``None`` when no
       guard was active.
    :returns: ``None``.

    .. note::
       A missing token is intentionally a no-op so callers can bracket nodes
       without branching on guard presence.
    """
    if token is not None:
        _EVALUATION_DEPTH.reset(token)


def internal_check_collection(size: int, span: SourceSpan) -> None:
    """Notify the active guard before materializing collection elements.

    :param size: Number of elements requested by the collection operation.
    :param span: Source range responsible for the collection operation.
    :returns: ``None``.

    .. note::
       Calls made without an installed guard are deliberately ignored, which
       keeps budget instrumentation optional for ordinary evaluation.
    """
    guard = _ACTIVE_GUARD.get()
    if guard is not None:
        guard.collection(size, span)
