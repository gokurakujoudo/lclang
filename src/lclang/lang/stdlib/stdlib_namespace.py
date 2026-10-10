"""Read-only attribute namespaces and deterministic stdlib Preset assembly.

Defines ``StdlibNamespace``, ``assemble_stdlib``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from lclang.error import LclStandardError, StandardLibraryErrorCode
from lclang.error.exception_base import LclAttributeError, LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang.runtime.preset import Preset
from lclang.lang.stdlib.builtin_manifest import (
    StdlibManifest,
    internal_validate_export_name,
)


@guard_constructor(LclValidationError, StandardLibraryErrorCode.E91_STDLIB_NAMESPACE_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class StdlibNamespace(Mapping[str, object]):
    """Expose immutable standard-library members by mapping and attribute.

    :param namespace: Public non-keyword diagnostic namespace identifier.
    :param members: String-keyed members copied in declaration order.
    :raises LclValidationError: If the namespace or a member name is invalid.

    .. note::
       Member objects are retained by reference and never called or awaited.
    """

    namespace: str
    members: Mapping[str, object]

    @guard_failure(LclValidationError, StandardLibraryErrorCode.E91_STDLIB_NAMESPACE_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate and detach an ordered member mapping."""
        internal_validate_export_name(self.namespace, "namespace")
        snapshot = dict(self.members)
        for name in snapshot:
            internal_validate_export_name(name, "entry name")
        object.__setattr__(self, "members", MappingProxyType(snapshot))

    @guard_failure(LclStandardError, StandardLibraryErrorCode.E91_STDLIB_NAMESPACE_NATIVE_FAILURE)
    def __getitem__(self, name: str) -> object:
        """Return one member by mapping key.

        :param name: Declared member name.
        :returns: Opaque reviewed member value.
        """
        return self.members[name]

    def __iter__(self) -> Iterator[str]:
        """Iterate member names in manifest declaration order.

        :returns: Iterator over declared member names.
        """
        return iter(self.members)

    def __len__(self) -> int:
        """Return the number of declared members.

        :returns: Number of namespace entries.
        """
        return len(self.members)

    def __repr__(self) -> str:
        """Return a stable summary without member implementation details.

        :returns: Namespace-name representation without mappings or addresses.
        """
        return f"StdlibNamespace(namespace={self.namespace!r})"

    @guard_failure(LclAttributeError, StandardLibraryErrorCode.E91_STDLIB_NAMESPACE_NATIVE_FAILURE)
    def __getattr__(self, name: str) -> object:
        """Return a declared member or a namespace-aware attribute error.

        :param name: Attribute-style member name.
        :returns: Opaque reviewed member value.
        :raises LclAttributeError: If no member has that name.
        """
        try:
            return self.members[name]
        except KeyError:
            message = f"standard-library namespace {self.namespace!r} has no {name!r}"
            raise LclAttributeError(
                message, code=StandardLibraryErrorCode.E91_NAMESPACE_ATTRIBUTE_NOT_FOUND
            ) from None


@guard_failure(LclStandardError, StandardLibraryErrorCode.E91_STDLIB_NAMESPACE_NATIVE_FAILURE)
def assemble_stdlib(
    manifests: Iterable[StdlibManifest],
    *,
    name: str = "stdlib",
) -> Preset:
    """Assemble reviewed manifests into one namespace Preset.

    :param manifests: Manifest iterable consumed exactly once in order.
    :param name: Non-empty name assigned to the resulting Preset.
    :returns: Immutable root namespace bindings for Frame construction.
    :raises LclValidationError: If an item is not a StdlibManifest.
    :raises LclValidationError: If root namespaces repeat or *name* is empty.

    .. note::
       Assembly performs no discovery, evaluation, call, import, or await.
    """
    roots: dict[str, StdlibNamespace] = {}
    for manifest in manifests:
        if not isinstance(manifest, StdlibManifest):
            raise LclValidationError(
                "stdlib assembly requires StdlibManifest values",
                code=StandardLibraryErrorCode.E91_STDLIB_ASSEMBLY_REQUIRES_STDLIBMANIFEST_VALUES,
            )
        if manifest.namespace in roots:
            raise LclValidationError(
                "duplicate standard-library namespace",
                code=StandardLibraryErrorCode.E91_DUPLICATE_STANDARD_LIBRARY_NAMESPACE,
            )
        members = {entry.name: entry.value for entry in manifest.entries}
        roots[manifest.namespace] = StdlibNamespace(manifest.namespace, members)
    return Preset(name, roots)
