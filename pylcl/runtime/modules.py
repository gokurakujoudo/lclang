"""Immutable named runtime definition snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pylcl.ast import LclAstNode
from pylcl.types import ModuleName


@dataclass(frozen=True, slots=True)
class Module:
    """Describe one immutable set of semantic variable definitions.

    :param name: Non-empty nominal module name.
    :param definitions: String-keyed semantic AST definitions to snapshot.
    :raises ValueError: If the module or any definition name is empty.

    .. note::
       The mapping is copied and exposed through a read-only proxy.
    """

    name: ModuleName
    definitions: Mapping[str, LclAstNode]

    def __post_init__(self) -> None:
        """Validate identifiers and detach definitions from caller mutation."""
        if not self.name:
            raise ValueError("module name cannot be empty")
        snapshot = dict(self.definitions)
        if any(not name for name in snapshot):
            raise ValueError("definition name cannot be empty")
        object.__setattr__(self, "definitions", MappingProxyType(snapshot))
