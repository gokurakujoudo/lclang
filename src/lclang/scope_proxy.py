"""Lazy attribute proxy for flat qualified Frame bindings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from lclang.errors import LclNameError
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
class FrameProxy:
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
