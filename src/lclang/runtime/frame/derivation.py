"""Convenience construction of independent child Frames."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from lclang.runtime.modules import Module
from lclang.types import FrameId

if TYPE_CHECKING:
    from lclang.runtime.frame.core import Frame


class FrameDerivationApi:
    """Provide concise child construction for concrete Frames.

    .. note::
       The concrete Frame supplies parent identity and runtime implementation.
    """

    def derive(
        self,
        module: Module,
        values: dict[str, object] = {},  # noqa: B006
    ) -> Frame:
        """Create a fresh child Frame borrowing this Frame as its parent.

        :param module: Immutable child definitions and nominal child identifier.
        :param values: Local host bindings copied into the child.
        :returns: Independent child Frame whose parent is this Frame.
        :raises TypeError: If *module* is not a Module or *values* is not a dict.
        :raises ValueError: If a local host-binding name is empty.

        .. note::
           The default and caller dictionary are never mutated or retained;
           Frame construction always snapshots the mapping.
           Prefer entering the returned child with ``async with`` so its owned
           state closes while this borrowed parent remains open.
        """
        from lclang.runtime.frame.core import Frame

        if not isinstance(module, Module):
            raise TypeError("derived frame module must be a Module")
        if not isinstance(values, dict):
            raise TypeError("derived frame values must be a dictionary")
        return Frame(
            module,
            FrameId(str(module.name)),
            values=values,
            parent=cast(Frame, self),
        )
