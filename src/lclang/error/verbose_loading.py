"""Task-local loading routes already visited by the configuration adapter.

Defines ``ACTIVE_LOADING_ROUTE``, ``scope_loading_route``.
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from lclang.error.diagnostic_records import ConfigLoadFrame

# Unitless route tuples inherit into owner tasks and are restored on every exit.
ACTIVE_LOADING_ROUTE: ContextVar[tuple[ConfigLoadFrame, ...]] = ContextVar(
    "lclang_loading_route", default=()
)


@contextmanager
def scope_loading_route(frame: ConfigLoadFrame) -> Generator[None]:
    """Retain one actual introduction while its target and descendants execute.

    :param frame: Already obtained source, directive and resolved target evidence.
    :returns: Scope restoring the earlier route even on cancellation.
    """
    token = ACTIVE_LOADING_ROUTE.set((*ACTIVE_LOADING_ROUTE.get(), frame))
    try:
        yield
    finally:
        ACTIVE_LOADING_ROUTE.reset(token)
