"""Immutable named runtime definition snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from lclang.ast import LclAstNode
from lclang.masking import normalize_masked_mapping
from lclang.scopes import real_binding_names, validate_binding_names, validate_real_conflicts
from lclang.types import ModuleName


@dataclass(frozen=True, slots=True)
class Module:
    """Describe one immutable set of semantic variable definitions.

    :param name: Non-empty nominal module name.
    :param definitions: String-keyed semantic AST definitions to snapshot.
    :param masked_names: Additional normalized definition names to redact.
    :raises ValueError: If the module or any definition name is empty.

    .. note::
       The mapping is copied and exposed through a read-only proxy.
    """

    name: ModuleName
    definitions: Mapping[str, LclAstNode]
    masked_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)

    def __post_init__(self) -> None:
        """Validate identifiers and detach definitions from caller mutation.

        :raises ValueError: If the module or a definition name is empty.
        """
        if not self.name:
            raise ValueError("module name cannot be empty")
        snapshot, masked_names = normalize_masked_mapping(
            self.definitions,
            self.masked_names,
        )
        if any(not name for name in snapshot):
            raise ValueError("definition name cannot be empty")
        validate_binding_names(snapshot)
        validate_real_conflicts(real_binding_names(snapshot, {}))
        object.__setattr__(self, "definitions", MappingProxyType(snapshot))
        object.__setattr__(self, "masked_names", masked_names)
