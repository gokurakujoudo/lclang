"""Read-only attribute namespaces and deterministic stdlib Preset assembly."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pylcl.runtime.presets import Preset
from pylcl.stdlib.manifest import (
    StdlibManifest,
    _validate_export_name,
)


@dataclass(frozen=True, slots=True)
class StdlibNamespace(Mapping[str, object]):
    """Expose immutable standard-library members by mapping and attribute.

    :param namespace: Public non-keyword diagnostic namespace identifier.
    :param members: String-keyed members copied in declaration order.
    :raises ValueError: If the namespace or a member name is invalid.

    .. note::
       Member objects are retained by reference and never called or awaited.
    """

    namespace: str
    members: Mapping[str, object]

    def __post_init__(self) -> None:
        """Validate and detach an ordered member mapping."""
        _validate_export_name(self.namespace, "namespace")
        snapshot = dict(self.members)
        for name in snapshot:
            _validate_export_name(name, "entry name")
        object.__setattr__(self, "members", MappingProxyType(snapshot))

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

    def __getattr__(self, name: str) -> object:
        """Return a declared member or a namespace-aware attribute error.

        :param name: Attribute-style member name.
        :returns: Opaque reviewed member value.
        :raises AttributeError: If no member has that name.
        """
        try:
            return self.members[name]
        except KeyError:
            message = f"standard-library namespace {self.namespace!r} has no {name!r}"
            raise AttributeError(message) from None


def assemble_stdlib(
    manifests: Iterable[StdlibManifest],
    *,
    name: str = "stdlib",
) -> Preset:
    """Assemble reviewed manifests into one namespace Preset.

    :param manifests: Manifest iterable consumed exactly once in order.
    :param name: Non-empty name assigned to the resulting Preset.
    :returns: Immutable root namespace bindings for Frame construction.
    :raises TypeError: If an item is not a StdlibManifest.
    :raises ValueError: If root namespaces repeat or *name* is empty.

    .. note::
       Assembly performs no discovery, evaluation, call, import, or await.
    """
    roots: dict[str, StdlibNamespace] = {}
    for manifest in manifests:
        if not isinstance(manifest, StdlibManifest):
            raise TypeError("stdlib assembly requires StdlibManifest values")
        if manifest.namespace in roots:
            raise ValueError("duplicate standard-library namespace")
        members = {entry.name: entry.value for entry in manifest.entries}
        roots[manifest.namespace] = StdlibNamespace(manifest.namespace, members)
    return Preset(name, roots)
