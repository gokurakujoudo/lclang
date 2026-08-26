"""Non-evaluating binding lookup for hierarchical runtime Frames."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from lclang.ast import LclAstNode
from lclang.runtime.frame.scoped import find_scoped_binding
from lclang.runtime.modules import Module


class LookupFrame(Protocol):
    """Describe the immutable inputs needed to locate a Frame binding.

    :param module: Local semantic definitions.
    :param values: Local host-value bindings.
    :param parent: Optional next ancestor in lookup order.

    .. note::
       The protocol excludes caches and evaluation so inspection has no effects.
    """

    module: Module
    values: Mapping[str, object]
    parent: object | None


def find_frame(frame: object, name: str) -> object | None:
    """Return the nearest Frame that owns a selected name binding.

    :param frame: First Frame in the child-to-parent search.
    :param name: Non-empty definition or host-value name.
    :returns: Nearest owning Frame, or ``None`` when the hierarchy lacks *name*.
    :raises ValueError: If *name* is empty.

    .. note::
       A local definition wins over a same-Frame value; either stops recursion.
    """
    if not name:
        raise ValueError("variable name cannot be empty")
    owner, _ = find_scoped_binding(frame, name)
    return owner


class FrameLookupApi:
    """Provide public, non-evaluating inspection over Frame lookup.

    .. note::
       Concrete Frames supply immutable module, value, and parent attributes.
    """

    def has(self, name: str) -> bool:
        """Report whether the hierarchy resolves a name.

        :param name: Non-empty definition or host-value name.
        :returns: ``True`` when recursive lookup selects any binding.
        :raises ValueError: If *name* is empty.

        .. note::
           Presence inspection never evaluates or caches a definition or value.
        """
        return find_frame(cast(LookupFrame, self), name) is not None

    def get_definition(self, name: str) -> LclAstNode | None:
        """Return the selected definition AST without evaluating it.

        :param name: Non-empty definition or host-value name.
        :returns: Nearest selected definition, or ``None`` for a value/miss.
        :raises ValueError: If *name* is empty.

        .. note::
           A nearer host value masks an ancestor definition with the same name.
        """
        owner = find_frame(self, name)
        if owner is None:
            return None
        return cast(LookupFrame, owner).module.definitions.get(name)
