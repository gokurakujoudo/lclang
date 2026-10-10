"""Immutable named runtime definition snapshots.

Defines ``Module``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from lclang.common.binding_mask import normalize_masked_mapping
from lclang.common.identifiers import ModuleName
from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.ast import LclAstNode, LclConstant
from lclang.lang.common.binding_declaration import real_binding_names
from lclang.lang.common.binding_names import validate_binding_names, validate_real_conflicts
from lclang.lang.common.frame_proxy_marker import FRAME_PROXY
from lclang.lang.common.namespace_names import (
    validate_namespace_conflicts,
    validate_namespace_names,
)


@guard_constructor(LclValidationError, RuntimeErrorCode.E11_MODULE_CONSTRUCTION_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class Module:
    """Describe one immutable set of semantic variable definitions.

    :param name: Non-empty nominal module name.
    :param definitions: String-keyed semantic AST definitions to snapshot.
    :param masked_names: Additional normalized definition names to redact.
    :param namespace_names: Explicit qualified namespace reservations.
    :raises LclValidationError: If the module or any definition name is empty.

    .. note::
       The mapping is copied and exposed through a read-only proxy.
    """

    name: ModuleName
    definitions: Mapping[str, LclAstNode]
    masked_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)
    namespace_names: frozenset[str] = field(default_factory=frozenset[str], kw_only=True)

    @guard_failure(LclValidationError, RuntimeErrorCode.E11_MODULE_CONSTRUCTION_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate identifiers and detach definitions from caller mutation.

        :raises LclValidationError: If the module or a definition name is empty.
        """
        if not self.name:
            raise LclValidationError(
                "module name cannot be empty", code=RuntimeErrorCode.E11_MODULE_NAME_CANNOT_BE_EMPTY
            )
        snapshot, masked_names = normalize_masked_mapping(
            self.definitions,
            self.masked_names,
        )
        if any(not name for name in snapshot):
            raise LclValidationError(
                "definition name cannot be empty",
                code=RuntimeErrorCode.E11_MODULE_NAME_CANNOT_BE_EMPTY,
            )
        validate_binding_names(snapshot)
        real_names = real_binding_names(snapshot, {})
        validate_real_conflicts(real_names)
        validate_namespace_names(self.namespace_names)
        validate_namespace_conflicts(self.namespace_names, real_names)
        for namespace in sorted(self.namespace_names):
            snapshot.setdefault(namespace, LclConstant(value=FRAME_PROXY))
        object.__setattr__(self, "definitions", MappingProxyType(snapshot))
        object.__setattr__(self, "masked_names", masked_names)

    @guard_failure(LclEvaluationError, RuntimeErrorCode.E11_MODULE_CONSTRUCTION_NATIVE_FAILURE)
    def mixin(self, other: Module, *, name: str | None = None) -> Module:
        """Compose two immutable Modules with right-side definition precedence.

        :param other: Module supplying replacement and additional definitions.
        :param name: Optional new non-empty module name; defaults to this name.
        :returns: New validated Module; both inputs and existing Frames stay unchanged.
        :raises LclValidationError: If *other* is not a Module or *name* is not text.
        :raises LclValidationError: If names or the combined binding structure are invalid.
        """
        if not isinstance(other, Module):
            raise LclValidationError(
                "Module mixin source must be a Module",
                code=RuntimeErrorCode.E11_MODULE_MIXIN_SOURCE_MUST_BE_A_MODULE,
            )
        if name is not None and not isinstance(name, str):
            raise LclValidationError(
                "Module name must be a string",
                code=RuntimeErrorCode.E11_MODULE_NAME_MUST_BE_A_STRING,
            )
        return Module(
            self.name if name is None else ModuleName(name),
            {**self.definitions, **other.definitions},
            masked_names=self.masked_names | other.masked_names,
            namespace_names=self.namespace_names | other.namespace_names,
        )
