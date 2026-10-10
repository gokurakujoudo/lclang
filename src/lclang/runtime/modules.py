"""Immutable named runtime definition snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from lclang.ast import LclAstNode, LclConstant
from lclang.masking import normalize_masked_mapping
from lclang.namespace_names import validate_namespace_conflicts, validate_namespace_names
from lclang.scopes import (
    FRAME_PROXY,
    real_binding_names,
    validate_binding_names,
    validate_real_conflicts,
)
from lclang.types import ModuleName


@dataclass(frozen=True, slots=True)
class Module:
    """Describe one immutable set of semantic variable definitions.

    :param name: Non-empty nominal module name.
    :param definitions: String-keyed semantic AST definitions to snapshot.
    :param masked_names: Additional normalized definition names to redact.
    :param namespace_names: Explicit qualified namespace reservations.
    :raises ValueError: If the module or any definition name is empty.

    .. note::
       The mapping is copied and exposed through a read-only proxy.
    """

    name: ModuleName
    definitions: Mapping[str, LclAstNode]
    masked_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)
    namespace_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)

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
        real_names = real_binding_names(snapshot, {})
        validate_real_conflicts(real_names)
        validate_namespace_names(self.namespace_names)
        validate_namespace_conflicts(self.namespace_names, real_names)
        for namespace in sorted(self.namespace_names):
            snapshot.setdefault(namespace, LclConstant(value=FRAME_PROXY))
        object.__setattr__(self, "definitions", MappingProxyType(snapshot))
        object.__setattr__(self, "masked_names", masked_names)

    def mixin(self, other: Module, *, name: str | None = None) -> Module:
        """Compose two immutable Modules with right-side definition precedence.

        :param other: Module supplying replacement and additional definitions.
        :param name: Optional new non-empty module name; defaults to this name.
        :returns: New validated Module; both inputs and existing Frames stay unchanged.
        :raises TypeError: If *other* is not a Module or *name* is not text.
        :raises ValueError: If names or the combined binding structure are invalid.
        """
        if not isinstance(other, Module):
            raise TypeError("Module mixin source must be a Module")
        if name is not None and not isinstance(name, str):
            raise TypeError("Module name must be a string")
        return Module(
            self.name if name is None else ModuleName(name),
            {**self.definitions, **other.definitions},
            masked_names=self.masked_names | other.masked_names,
            namespace_names=self.namespace_names | other.namespace_names,
        )
