"""Immutable reviewed standard-library entry and namespace manifests.

Defines ``internal_validate_export_name``, ``StdlibEntry``, ``StdlibManifest``.
"""

from __future__ import annotations

import keyword
from collections.abc import Iterable
from dataclasses import dataclass

from lclang.error import StandardLibraryErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure

# Unitless reserved names come from namespace inspection methods; excluding them prevents module
# members from shadowing that API.
_RESERVED_NAMES = frozenset({"get", "items", "keys", "members", "namespace", "values"})


def internal_validate_export_name(name: str, label: str) -> None:
    """Reject names unsafe for public mapping/attribute namespaces.

    :param name: Candidate public identifier.
    :param label: Human-readable field label used in diagnostics.
    :raises LclValidationError: If the candidate violates namespace policy.
    """
    if (
        not name.isidentifier()
        or keyword.iskeyword(name)
        or name.startswith("_")
        or name in _RESERVED_NAMES
    ):
        raise LclValidationError(
            f"invalid standard-library {label}: {name!r}",
            code=StandardLibraryErrorCode.E11_INVALID_STANDARD_LIBRARY,
        )


@guard_constructor(LclValidationError, StandardLibraryErrorCode.E11_BUILTIN_MANIFEST_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class StdlibEntry:
    """Describe one reviewed opaque standard-library export.

    :param name: Public non-keyword attribute identifier.
    :param value: Opaque exported value retained by reference.
    :param summary: Non-blank one-line review summary.
    :raises LclValidationError: If the name or summary violates manifest policy.

    .. note::
       Construction never calls, imports, copies, or awaits *value*.
    """

    name: str
    value: object
    summary: str

    @guard_failure(LclValidationError, StandardLibraryErrorCode.E11_BUILTIN_MANIFEST_NATIVE_FAILURE)
    def __post_init__(self) -> None:
        """Validate stable public metadata without touching the value.

        :raises LclValidationError: If the name or summary violates manifest policy.
        """
        internal_validate_export_name(self.name, "entry name")
        if not self.summary.strip() or "\n" in self.summary or "\r" in self.summary:
            raise LclValidationError(
                "standard-library summary must be one non-blank line",
                code=StandardLibraryErrorCode.E11_STANDARD_LIBRARY_SUMMARY_MUST_BE_ONE_NON_BLANK_LINE,
            )


@guard_constructor(LclValidationError, StandardLibraryErrorCode.E11_BUILTIN_MANIFEST_NATIVE_FAILURE)
@guard_constructor(LclValidationError, StandardLibraryErrorCode.E11_BUILTIN_MANIFEST_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True, init=False)
class StdlibManifest:
    """Describe one ordered root standard-library namespace.

    :param namespace: Public non-keyword root identifier.
    :param entries: Entry iterable consumed once in declaration order.
    :raises LclValidationError: If an item is not a StdlibEntry.
    :raises LclValidationError: If the namespace is invalid or entry names repeat.

    .. note::
       Entries become an immutable tuple; their opaque values remain shallow.
    """

    namespace: str
    entries: tuple[StdlibEntry, ...]

    def __init__(self, namespace: str, entries: Iterable[StdlibEntry]) -> None:
        """Consume, validate, and detach one manifest declaration.

        :param namespace: Public non-keyword root identifier.
        :param entries: Entry iterable consumed once in declaration order.
        :raises LclValidationError: If an item is not a :class:`StdlibEntry`.
        :raises LclValidationError: If the namespace is invalid or names repeat.
        """
        internal_validate_export_name(namespace, "namespace")
        snapshot = tuple(entries)
        if any(not isinstance(entry, StdlibEntry) for entry in snapshot):
            raise LclValidationError(
                "manifest entries must be StdlibEntry values",
                code=StandardLibraryErrorCode.E11_MANIFEST_ENTRIES_MUST_BE_STDLIBENTRY_VALUES,
            )
        names = tuple(entry.name for entry in snapshot)
        if len(set(names)) != len(names):
            raise LclValidationError(
                "duplicate standard-library entry name",
                code=StandardLibraryErrorCode.E11_DUPLICATE_STANDARD_LIBRARY_ENTRY_NAME,
            )
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "entries", snapshot)
