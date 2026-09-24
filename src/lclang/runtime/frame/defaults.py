# Shared implementation modules intentionally access owner state.
# pyright: reportPrivateUsage=false

"""Owned default Frames and task-local fallback lookup scopes."""

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lclang.ast import LclCall, LclConstant
from lclang.defaults import NO_DEFAULT, DefaultBinding

if TYPE_CHECKING:
    from lclang.runtime.frame.frame import Frame


@dataclass(frozen=True, slots=True)
class DefaultScope:
    """Associate one execution's root and definition owners with defaults.

    :param root: Borrowed execution root.
    :param owners: Existing definition-owning ancestor Frames.
    :param defaults: Independently owned lowest-priority Frame.
    """

    root: Frame
    owners: frozenset[Frame]
    defaults: Frame


# Unitless task-local scope stack; ContextVar isolation prevents concurrent
# executions from changing each other's defaults or borrowed Frame hierarchy.
DEFAULT_SCOPES: ContextVar[tuple[DefaultScope, ...]] = ContextVar("workflow_defaults", default=())


def create_default_frame(bindings: Mapping[str, DefaultBinding]) -> Frame:
    """Create lazy factory definitions and reference-preserving literal bindings.

    :param bindings: Normalized or masked names with default declarations.
    :returns: Caller-owned Frame with fresh single-flight result/failure caches.
    """
    from lclang.runtime.frame.frame import Frame
    from lclang.runtime.modules import Module
    from lclang.types import ModuleName

    definitions = {
        name: LclCall(function=LclConstant(value=binding.factory))
        for name, binding in bindings.items()
        if binding.factory is not None
    }
    values = {
        name: binding.value for name, binding in bindings.items() if binding.value is not NO_DEFAULT
    }
    return Frame(Module(ModuleName("variable_defaults"), definitions), values=values)


def attach_defaults(frame: Frame, defaults: Frame) -> None:
    """Associate an owned CLI hierarchy with its separate fallback Frame.

    :param frame: Root of the owned invocation hierarchy.
    :param defaults: Default Frame closed by the same invocation owner.
    """
    frame._default_frame = defaults


@contextmanager
def default_scope(root: Frame, defaults: Frame) -> Generator[None]:
    """Expose fallback bindings for one run without changing borrowed Frames.

    :param root: Borrowed workflow execution root.
    :param defaults: Owned default Frame for this run.
    :returns: Context manager resetting task-local lookup policy on exit.
    """
    from lclang.runtime.frame.binding_lookup import walk_hierarchy

    scope = DefaultScope(root, frozenset(walk_hierarchy(root)), defaults)
    token = DEFAULT_SCOPES.set((*DEFAULT_SCOPES.get(), scope))
    try:
        yield
    finally:
        DEFAULT_SCOPES.reset(token)


def default_frame_for(frame: Frame) -> Frame | None:
    """Find the nearest active default environment for a requesting Frame.

    :param frame: Requesting or lexical definition-owning Frame.
    :returns: Active execution defaults, owned invocation defaults, or None.
    """
    from lclang.runtime.frame.binding_lookup import walk_hierarchy

    for scope in reversed(DEFAULT_SCOPES.get()):
        if frame in scope.owners or scope.root in walk_hierarchy(frame):
            return scope.defaults
    for owner in walk_hierarchy(frame):
        if owner._default_frame is not None:
            return owner._default_frame
    return None
