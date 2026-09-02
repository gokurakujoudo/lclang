"""Lazy attribute proxy for flat qualified Frame bindings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Protocol

from lclang.errors import LclNameError
from lclang.scopes import ScopedProxyValue
from lclang.source import SourceSpan


class ProxyFrame(Protocol):
    """Describe the Frame lookup used by a proxy."""

    async def get_resolved(self, name: str, span: SourceSpan | None) -> object:
        """Resolve one complete qualified name.

        :param name: Complete flat binding key.
        :param span: Optional source span for structured diagnostics.
        :returns: Fully auto-awaited terminal value.
        """
        ...


@dataclass(frozen=True, slots=True)
class FrameProxy(ScopedProxyValue):
    """Expose qualified children through one requesting Frame.

    :param frame: Frame where every terminal lookup begins.
    :param path: Non-empty complete prefix segments.
    :param trace: Optional qualified terminal dependency recorder.
    """

    frame: ProxyFrame
    path: tuple[str, ...]
    trace: Callable[[str, SourceSpan], None] | None = None

    def __repr__(self) -> str:
        """Return a stable prefix-oriented representation.

        :returns: Qualified proxy label.
        """
        return f"FrameProxy({'.'.join(self.path)})"

    def __getattr__(self, name: str) -> Any:
        """Return a nested proxy or terminal lookup awaitable.

        :param name: Python attribute segment.
        :returns: Nested proxy or coroutine resolving a real leaf.
        :raises AttributeError: If the qualified child is absent.
        """
        from lclang.runtime.frame.scoped import find_scoped_binding

        if name.startswith("_"):
            raise AttributeError(name)
        full = ".".join((*self.path, name))
        owner, kind = find_scoped_binding(self.frame, full)
        if owner is None:
            raise AttributeError(full)
        if kind == "proxy":
            return FrameProxy(self.frame, (*self.path, name))
        return self.frame.get_resolved(full, None)

    def __getitem__(self, name: str) -> Any:
        """Return the same child selected by attribute access.

        :param name: Direct child identifier.
        :returns: Nested proxy or coroutine resolving a real leaf.
        :raises TypeError: If *name* is not text.
        :raises AttributeError: If the qualified child is absent.
        """
        if not isinstance(name, str):
            raise TypeError("FrameProxy index must be text")
        return getattr(self, name)

    async def get(self, name: str, default: object = None) -> object:
        """Resolve one direct child or return a default when it is absent.

        :param name: Direct child name.
        :param default: Value returned unchanged when the child is absent.
        :returns: Nested proxy, resolved terminal value, or *default*.
        :raises TypeError: If *name* is not text.
        """
        from lclang.runtime.frame.scoped import find_scoped_binding

        if not isinstance(name, str):
            raise TypeError("FrameProxy child name must be text")
        full = ".".join((*self.path, name))
        owner, kind = find_scoped_binding(self.frame, full)
        if owner is None:
            return default
        if kind == "proxy":
            return FrameProxy(self.frame, (*self.path, name), self.trace)
        return await self.frame.get_resolved(full, None)

    async def field_names(self) -> list[str]:
        """Return alphabetically sorted identifiers for direct proxy children.

        :returns: Effective direct child names across the Frame hierarchy.
        """
        from lclang.runtime.frame.scoped import hierarchy_binding_names

        prefix = ".".join(self.path) + "."
        names = {
            name[len(prefix) :].split(".", 1)[0]
            for name in hierarchy_binding_names(self.frame)
            if name.startswith(prefix) and len(name) > len(prefix)
        }
        return sorted(names)

    async def as_record[T](self, cls: type[T]) -> T:
        """Materialize direct children into one dataclass instance.

        :param cls: Dataclass type used as the record template.
        :returns: New dataclass instance containing present child values.
        :raises TypeError: If *cls* is not a dataclass type or required fields
           remain absent.
        :raises Exception: If resolving a present child fails.
        """
        if not isinstance(cls, type) or not is_dataclass(cls):
            raise TypeError("FrameProxy record type must be a dataclass")
        available = set(await self.field_names())
        values: dict[str, object] = {}
        for item in fields(cls):
            if item.init and item.name in available:
                values[item.name] = await self.get(item.name)
        return cls(**values)

    async def resolve_attribute(
        self,
        name: str,
        *,
        safe: bool,
        span: SourceSpan,
    ) -> object:
        """Resolve one LCL attribute with proxy-aware safe semantics.

        :param name: Attribute segment.
        :param safe: Whether missing descendants become ``None``.
        :param span: Complete attribute source span.
        :returns: Nested proxy, terminal value, or ``None``.
        :raises LclNameError: If an ordinary scoped child is absent.
        """
        from lclang.runtime.frame.scoped import find_scoped_binding

        full = ".".join((*self.path, name))
        owner, kind = find_scoped_binding(self.frame, full)
        if owner is None:
            if safe:
                return None
            raise LclNameError(f"unknown variable: {full}", span=span)
        if kind == "proxy":
            return FrameProxy(self.frame, (*self.path, name), self.trace)
        if self.trace is not None:
            self.trace(full, span)
        return await self.frame.get_resolved(full, span)

    def with_trace(self, trace: Callable[[str, SourceSpan], None]) -> FrameProxy:
        """Return this proxy with one dynamic dependency recorder.

        :param trace: Callback receiving qualified terminal names and spans.
        :returns: Equivalent immutable traced proxy.
        """
        return FrameProxy(self.frame, self.path, trace)
