"""Frame adapters bind language-independent factory markers to requesting scopes."""

import pytest

from lclang.lang import Frame, FrameProxy, define_frame, define_module
from lclang.utils import ScopedProxyFactory, ScopedProxyValue


class NamespaceFactory(ScopedProxyFactory):
    """Expose the requesting Frame's qualified children as a scoped value."""

    def bind(self, frame: Frame, path: tuple[str, ...]) -> ScopedProxyValue:
        return FrameProxy(frame, path)


@pytest.mark.asyncio
async def test_custom_utility_factory_keeps_requesting_frame_overrides() -> None:
    """A generic factory follows the same child precedence as the environment adapter."""
    factory = NamespaceFactory()
    async with (
        define_frame(preset={"service": factory, "service.answer": 21}) as parent,
        parent.derive(define_module("child", {}), values={"service.answer": 42}) as child,
    ):
        parent_view = await parent.get("service")
        child_view = await child.get("service")
        assert isinstance(parent_view, FrameProxy) and isinstance(child_view, FrameProxy)
        assert await parent_view.get("answer") == 21
        assert await child_view.get("answer") == 42
