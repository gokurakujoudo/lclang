"""Task-local verbose destinations and detached execution context.

Defines ``VerboseLogger``, ``VerboseContext``, ``allocate_verbose_id``,
``is_verbose_enabled``, ``scope_verbose_request``, ``scope_verbose_evaluation``.
"""

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from itertools import count
from threading import Lock
from typing import Protocol


class VerboseLogger(Protocol):
    """Describe the shared standard-library and lclang logging operations."""

    def isEnabledFor(self, level: int) -> bool:
        """Check whether the destination accepts a severity.

        :param level: Standard-library numeric severity.
        :returns: Whether producers should construct diagnostic values.
        """
        ...

    def debug(
        self,
        msg: object,
        *args: object,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """Send a DEBUG record through the borrowed destination.

        :param msg: Message or standard-library formatting template.
        :param args: Deferred template arguments.
        :param stacklevel: Standard-library caller offset.
        :param extra: Structured standard-library record fields.
        """
        ...


@dataclass(frozen=True, slots=True)
class VerboseContext:
    """Retain text-only context without holding Frames or host values.

    :param evaluation_id: Current evaluation identifier, or None outside evaluation.
    :param request_path: Actual nested definition requests in encounter order.
    :param requester: Requesting Frame identifier when available.
    :param owner: Selected binding owner identifier when available.
    :param lookup_path: Frame identifiers traversed by the existing lookup.
    :param execution: Actual selected execution or lookup source.
    """

    evaluation_id: str | None = None
    request_path: tuple[str, ...] = ()
    requester: str | None = None
    owner: str | None = None
    lookup_path: tuple[str, ...] = ()
    execution: str | None = None


# Unitless task-local defaults leave ordinary execution silent and context-free.
ACTIVE_VERBOSE_LOGGER: ContextVar[VerboseLogger | None] = ContextVar(
    "lclang_active_verbose_logger", default=None
)
EMPTY_VERBOSE_CONTEXT = VerboseContext()
ACTIVE_VERBOSE_CONTEXT: ContextVar[VerboseContext] = ContextVar(
    "lclang_verbose_context", default=EMPTY_VERBOSE_CONTEXT
)
# Process-local monotonically increasing identifiers need no clock or randomness.
# The lock preserves uniqueness across producer threads; identifiers have no units.
VERBOSE_IDS = count(1)
VERBOSE_ID_LOCK = Lock()


def allocate_verbose_id(prefix: str) -> str:
    """Allocate a short process-local diagnostic identifier.

    :param prefix: Evaluation or failure discriminator supplied by the caller.
    :returns: Prefix followed by a monotonically increasing decimal number.
    """
    with VERBOSE_ID_LOCK:
        return f"{prefix}{next(VERBOSE_IDS)}"


def is_verbose_enabled() -> bool:
    """Check the current destination before trace-only rendering.

    :returns: Whether DEBUG is accepted by the borrowed logger.
    """
    logger = ACTIVE_VERBOSE_LOGGER.get()
    return logger is not None and logger.isEnabledFor(10)


@contextmanager
def scope_verbose_request(
    name: str, requester: str, owner: str | None, lookup_path: tuple[str, ...], execution: str
) -> Generator[None]:
    """Bind one already-selected lookup to inherited evaluation tasks.

    :param name: Actual requested binding name.
    :param requester: Requesting Frame identifier.
    :param owner: Selected binding owner, or None when missing.
    :param lookup_path: Already-observed hierarchy path.
    :param execution: Selected source or cache state.
    :returns: Context manager restoring the prior request on every exit.
    """
    previous = ACTIVE_VERBOSE_CONTEXT.get()
    path = previous.request_path
    token = ACTIVE_VERBOSE_CONTEXT.set(
        replace(
            previous,
            request_path=path if path[-1:] == (name,) else (*path, name),
            requester=requester,
            owner=owner,
            lookup_path=lookup_path,
            execution=execution,
        )
    )
    try:
        yield
    finally:
        ACTIVE_VERBOSE_CONTEXT.reset(token)


@contextmanager
def scope_verbose_evaluation(name: str) -> Generator[None]:
    """Associate reads with one expression evaluation without owning its task.

    :param name: Actual evaluated definition or expression label.
    :returns: Context manager restoring the parent evaluation on every exit.
    """
    if not is_verbose_enabled():
        yield
        return
    previous = ACTIVE_VERBOSE_CONTEXT.get()
    path = previous.request_path
    token = ACTIVE_VERBOSE_CONTEXT.set(
        replace(
            previous,
            evaluation_id=allocate_verbose_id("E"),
            request_path=path if path[-1:] == (name,) else (*path, name),
        )
    )
    try:
        yield
    finally:
        ACTIVE_VERBOSE_CONTEXT.reset(token)
