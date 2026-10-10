"""Validation of explicit, possibly empty configuration namespaces."""

from collections.abc import Iterable

from lclang.scopes import validate_qualified_name


def validate_namespace_names(names: frozenset[str]) -> None:
    """Validate immutable explicit namespace metadata.

    :param names: Qualified namespace names, including empty namespaces.
    :raises TypeError: If the set or a namespace has an unsupported type.
    :raises ValueError: If a namespace is malformed or reserved.
    """
    if not isinstance(names, frozenset):
        raise TypeError("namespace names must be a frozenset")
    for name in names:
        validate_qualified_name(name)
        if name.startswith("__"):
            raise ValueError("namespace name cannot be reserved")


def validate_namespace_conflicts(names: Iterable[str], real_names: Iterable[str]) -> None:
    """Reject ordinary values at or above an explicit namespace.

    :param names: Namespace reservations visible in one configuration or hierarchy.
    :param real_names: Ordinary effective binding names.
    :raises ValueError: If an ordinary binding occupies a namespace or its ancestor.
    """
    selected = set(real_names)
    for namespace in sorted(names):
        parts = namespace.split(".")
        for index in range(1, len(parts) + 1):
            name = ".".join(parts[:index])
            if name in selected:
                error = ValueError(f"namespace {namespace!r} conflicts with binding {name!r}")
                error.__dict__["binding_names"] = (namespace, name)
                raise error
