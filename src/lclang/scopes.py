"""Shared scoped-binding marker and name validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

# LCL words that cannot be used as reference identifiers.
LCL_RESERVED_NAMES = frozenset(
    {
        "and",
        "or",
        "not",
        "if",
        "else",
        "for",
        "in",
        "is",
        "true",
        "false",
        "none",
        "True",
        "False",
        "None",
        "raise",
        "try",
        "except",
        "finally",
        "assert",
        "with",
        "as",
        "FRAME_PROXY",
    }
)


class FrameProxyMarker:
    """Represent the singleton declaration value for a scoped prefix.

    .. note::
       Runtime proxies are separate caller-bound :class:`FrameProxy` values.
    """

    def __repr__(self) -> str:
        """Return the canonical LCL spelling.

        :returns: Stable proxy declaration source.
        """
        return "FRAME_PROXY"


# Public singleton declaring that one binding is a proxy prefix.
FRAME_PROXY = FrameProxyMarker()


class ScopedProxyValue:
    """Mark a caller-bound scoped value with custom attribute resolution."""


class ScopedProxyFactory:
    """Mark a utility that creates caller-bound scoped values."""


def is_frame_proxy(value: object) -> bool:
    """Report whether a value is the public proxy declaration singleton.

    :param value: Candidate AST or host value.
    :returns: Whether *value* declares a Frame proxy.
    """
    from lclang.ast import LclConstant

    return value is FRAME_PROXY or (
        isinstance(value, LclConstant) and value.value is FRAME_PROXY
    )


def scoped_proxy_factory(value: object) -> ScopedProxyFactory | None:
    """Return a scoped utility factory carried by a host or constant value.

    :param value: Candidate semantic or host value.
    :returns: Factory instance, or ``None`` for an ordinary value.
    """
    return value if isinstance(value, ScopedProxyFactory) else None


def validate_qualified_name(name: str) -> tuple[str, ...]:
    """Validate and split one LCL-qualified binding name.

    :param name: Candidate dot-separated name.
    :returns: Non-empty identifier segments.
    :raises TypeError: If *name* is not text.
    :raises ValueError: If a segment is not an LCL identifier.
    """
    if not isinstance(name, str):
        raise TypeError("binding name must be a string")
    parts = tuple(name.split("."))
    if not parts or any(
        not part or not part.isidentifier() or part in LCL_RESERVED_NAMES
        for part in parts
    ):
        raise ValueError(f"invalid qualified binding name: {name}")
    return parts


def validate_binding_names(names: Iterable[str]) -> None:
    """Validate dotted names while retaining legacy flat host keys.

    :param names: Binding names to inspect.
    :raises ValueError: If a dotted name is malformed.
    """
    for name in names:
        if "." in name:
            validate_qualified_name(name)


def real_binding_names(
    definitions: Mapping[str, object],
    values: Mapping[str, object],
) -> tuple[str, ...]:
    """Return real local names after definition precedence.

    :param definitions: Local semantic definitions.
    :param values: Local host values.
    :returns: Real names in stable definition-then-value order.
    """
    result = [
        name
        for name, node in definitions.items()
        if not is_frame_proxy(node) and scoped_proxy_factory(node) is None
    ]
    result.extend(
        name
        for name, value in values.items()
        if name not in definitions
        and not is_frame_proxy(value)
        and scoped_proxy_factory(value) is None
    )
    return tuple(result)


def validate_real_conflicts(names: Iterable[str]) -> None:
    """Reject strict ancestor relationships among real binding names.

    :param names: Effective real names; exact duplicates are allowed.
    :raises ValueError: If one real name is a strict dotted prefix of another.
    """
    unique = tuple(dict.fromkeys(names))
    selected = set(unique)
    for name in unique:
        parts = name.split(".")
        for index in range(1, len(parts)):
            ancestor = ".".join(parts[:index])
            if ancestor in selected:
                raise ValueError(
                    f"scoped binding conflict between {ancestor!r} and {name!r}"
                )
