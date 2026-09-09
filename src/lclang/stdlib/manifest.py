"""Immutable reviewed standard-library entry and namespace manifests."""

from __future__ import annotations

import keyword
from collections.abc import Iterable
from dataclasses import dataclass

# Unitless reserved names come from namespace inspection methods; excluding them prevents module
# members from shadowing that API.
_RESERVED_NAMES = frozenset({"get", "items", "keys", "members", "namespace", "values"})


def internal_validate_export_name(name: str, label: str) -> None:
    """Reject names unsafe for public mapping/attribute namespaces.

    :param name: Candidate public identifier.
    :param label: Human-readable field label used in diagnostics.
    :raises ValueError: If the candidate violates namespace policy.
    """
    if (
        not name.isidentifier()
        or keyword.iskeyword(name)
        or name.startswith("_")
        or name in _RESERVED_NAMES
    ):
        raise ValueError(f"invalid standard-library {label}: {name!r}")


@dataclass(frozen=True, slots=True)
class StdlibEntry:
    """Describe one reviewed opaque standard-library export.

    :param name: Public non-keyword attribute identifier.
    :param value: Opaque exported value retained by reference.
    :param summary: Non-blank one-line review summary.
    :raises ValueError: If the name or summary violates manifest policy.

    .. note::
       Construction never calls, imports, copies, or awaits *value*.
    """

    name: str
    value: object
    summary: str

    def __post_init__(self) -> None:
        """Validate stable public metadata without touching the value.

        :raises ValueError: If the name or summary violates manifest policy.
        """
        internal_validate_export_name(self.name, "entry name")
        if not self.summary.strip() or "\n" in self.summary or "\r" in self.summary:
            raise ValueError("standard-library summary must be one non-blank line")


@dataclass(frozen=True, slots=True, init=False)
class StdlibManifest:
    """Describe one ordered root standard-library namespace.

    :param namespace: Public non-keyword root identifier.
    :param entries: Entry iterable consumed once in declaration order.
    :raises TypeError: If an item is not a StdlibEntry.
    :raises ValueError: If the namespace is invalid or entry names repeat.

    .. note::
       Entries become an immutable tuple; their opaque values remain shallow.
    """

    namespace: str
    entries: tuple[StdlibEntry, ...]

    def __init__(self, namespace: str, entries: Iterable[StdlibEntry]) -> None:
        """Consume, validate, and detach one manifest declaration.

        :param namespace: Public non-keyword root identifier.
        :param entries: Entry iterable consumed once in declaration order.
        :raises TypeError: If an item is not a :class:`StdlibEntry`.
        :raises ValueError: If the namespace is invalid or names repeat.
        """
        internal_validate_export_name(namespace, "namespace")
        snapshot = tuple(entries)
        if any(not isinstance(entry, StdlibEntry) for entry in snapshot):
            raise TypeError("manifest entries must be StdlibEntry values")
        names = tuple(entry.name for entry in snapshot)
        if len(set(names)) != len(names):
            raise ValueError("duplicate standard-library entry name")
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "entries", snapshot)
