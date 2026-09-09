"""Task-local internal verbose diagnostics."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from lclang.masking import MASKED_VALUE
from lclang.utils.representation import safe_repr

type ValueRenderer = Callable[[], str]

# Logger selected only for the current invocation and its child Tasks.
# Unitless diagnostic context keys are local to this implementation. Logger state starts at None
# and masking at False so ordinary execution remains silent and unmasked until an invocation
# explicitly opts in.
ACTIVE_VERBOSE_LOGGER: ContextVar[logging.Logger | None] = ContextVar(
    "lclang_active_verbose_logger",
    default=None,
)
# Task-local switch preventing diagnostic payload rendering.
ACTIVE_MASKED_VALUE: ContextVar[bool] = ContextVar("lclang_active_masked_value", default=False)


def internal_verbose_enabled() -> bool:
    """Report whether the current task has an active verbose logger.

    :returns: Whether trace values should be rendered and emitted.
    """
    return ACTIVE_VERBOSE_LOGGER.get() is not None


def internal_render_value(
    value: object,
    renderer: ValueRenderer | None = None,
    *,
    masked: bool = False,
) -> str:
    """Render one value without allowing its representation to break tracing.

    :param value: Value whose concrete type labels the output.
    :param renderer: Optional canonical payload renderer used instead of ``repr``.
    :param masked: Whether to return the stable redaction marker directly.
    :returns: One bounded physical line using ``(type) value`` syntax.
    """
    if masked or ACTIVE_MASKED_VALUE.get():
        return MASKED_VALUE
    payload = safe_repr(
        value, renderer=None if renderer is None else lambda value: renderer(),
    )
    return f"({type(value).__name__}) {payload}"


def internal_trace(stage: str, message: str) -> None:
    """Emit one already-rendered internal diagnostic when tracing is active.

    :param stage: Stable lowercase trace category.
    :param message: One-line diagnostic payload.
    :returns: ``None``.
    """
    logger = ACTIVE_VERBOSE_LOGGER.get()
    if logger is not None:
        logger.debug("[lclang.%s] %s", stage, message, stacklevel=2)


@contextmanager
def internal_verbose_scope(logger: logging.Logger | None) -> Iterator[None]:
    """Activate one logger for the current context and inherited child Tasks.

    :param logger: Invocation logger, or ``None`` to retain silent behavior.
    :returns: Context manager iterator restoring the previous task-local logger.
    """
    if logger is None:
        yield
        return
    token = ACTIVE_VERBOSE_LOGGER.set(logger)
    try:
        yield
    finally:
        ACTIVE_VERBOSE_LOGGER.reset(token)


@contextmanager
def internal_masked_scope(masked: bool = True) -> Iterator[None]:
    """Suppress diagnostic payload rendering within one task-local scope.

    :param masked: Whether payloads should use the stable masked marker.
    :returns: Context manager iterator restoring prior masking state.
    """
    if not masked:
        yield
        return
    token = ACTIVE_MASKED_VALUE.set(True)
    try:
        yield
    finally:
        ACTIVE_MASKED_VALUE.reset(token)
