"""Synchronous and asynchronous context-manager evaluation."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, cast

from lclang.ast import LclWith
from lclang.lang.evaluator._types import EvaluateNode
from lclang.lang.evaluator.awaitables import resolve_awaitable
from lclang.lang.evaluator.context import Resolver, ScopedResolver

type ExitMethod = Callable[
    [type[BaseException] | None, BaseException | None, TracebackType | None],
    object,
]


class InternalSyncProtocol(Protocol):
    """Describe the synchronous context-manager methods used by evaluation.

    .. note::
       The protocol is used only after asynchronous protocol detection has
       failed; its exit method may still return an awaitable value.
    """

    __enter__: Callable[[], object]
    __exit__: ExitMethod


async def internal_evaluate_with(
    node: LclWith,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Evaluate every context item and then the protected body.

    :param node: ``with`` AST node containing context items and body.
    :param resolver: Resolver providing the surrounding lexical scope.
    :param evaluate: Recursive evaluator for contexts and the body.
    :returns: Result produced by the protected body, or ``None`` when an exit
       method suppresses an exception.

    .. note::
       Nested acquisition is unwound in reverse order so each manager exits
       after all managers acquired inside it.
    """
    return await internal_enter_item(node, 0, resolver, evaluate)


async def internal_enter_item(
    node: LclWith,
    index: int,
    resolver: Resolver,
    evaluate: EvaluateNode,
) -> object:
    """Acquire one context item and recursively evaluate the remaining items.

    :param node: ``with`` AST node being traversed.
    :param index: Zero-based item position to acquire next.
    :param resolver: Resolver for the current lexical scope.
    :param evaluate: Recursive evaluator for context expressions and the body.
    :returns: Protected-body result, or ``None`` if an exit suppresses failure.

    .. note::
       Bound targets use a layered resolver, and every acquired manager gets an
       exit call even when a nested body or acquisition raises.
    """
    if index == len(node.items):
        return await evaluate(node.body, resolver)
    item = node.items[index]
    manager = await evaluate(item.context, resolver)
    value, exit_method = await internal_acquire(manager)
    scope = resolver
    if item.target is not None:
        scope = ScopedResolver({str(item.target): value}, resolver)
    try:
        result = await internal_enter_item(node, index + 1, scope, evaluate)
    except BaseException as error:
        suppressed = await resolve_awaitable(
            exit_method(type(error), error, error.__traceback__),
        )
        if bool(suppressed):
            return None
        raise
    await resolve_awaitable(exit_method(None, None, None))
    return result


async def internal_acquire(manager: object) -> tuple[object, ExitMethod]:
    """Acquire a synchronous or asynchronous context manager.

    :param manager: Evaluated context-manager candidate.
    :returns: Entered context value and its compatible exit callback.

    .. note::
       Asynchronous ``__aenter__``/``__aexit__`` takes precedence when both
       protocols are present; all callback results are resolved as awaitables.
    """
    async_enter = getattr(manager, "__aenter__", None)
    async_exit = getattr(manager, "__aexit__", None)
    if callable(async_enter) and callable(async_exit):
        value = await resolve_awaitable(async_enter())
        return value, cast(ExitMethod, async_exit)
    sync_manager = cast(InternalSyncProtocol, manager)
    value = await resolve_awaitable(sync_manager.__enter__())
    return value, sync_manager.__exit__
