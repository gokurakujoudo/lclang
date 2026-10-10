"""Shared scoped-binding marker and name validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.core import Code as core_codes

# LCL words that cannot be used as reference identifiers.
# Unitless reserved names and the proxy sentinel implement the scoped-binding contract. The
# reserved spellings protect framework metadata; one identity marker distinguishes proxy intent
# from ordinary values.
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
        "NEED_OVERRIDE",
        "RUNTIME_OVERRIDE",
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


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def is_frame_proxy(value: object) -> bool:
    """Report whether a value is the public proxy declaration singleton.

    :param value: Candidate AST or host value.
    :returns: Whether *value* declares a Frame proxy.
    """
    from lclang.ast import LclConstant

    return value is FRAME_PROXY or (isinstance(value, LclConstant) and value.value is FRAME_PROXY)


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def scoped_proxy_factory(value: object) -> ScopedProxyFactory | None:
    """Return a scoped utility factory carried by a host or constant value.

    :param value: Candidate semantic or host value.
    :returns: Factory instance, or ``None`` for an ordinary value.
    """
    return value if isinstance(value, ScopedProxyFactory) else None


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def validate_qualified_name(name: str) -> tuple[str, ...]:
    """Validate and split one LCL-qualified binding name.

    :param name: Candidate dot-separated name.
    :returns: Non-empty identifier segments.
    :raises LclValidationError: If *name* is not text.
    :raises LclValidationError: If a segment is not an LCL identifier.
    """
    if not isinstance(name, str):
        raise LclValidationError(
            "binding name must be a string", code=core_codes.E41_BINDING_NAME_MUST_BE_A_STRING
        )
    parts = tuple(name.split("."))
    if not parts or any(
        not part or not part.isidentifier() or part in LCL_RESERVED_NAMES for part in parts
    ):
        raise LclValidationError(
            f"invalid qualified binding name: {name}",
            code=core_codes.E41_INVALID_QUALIFIED_BINDING_NAME_VALUE,
        )
    return parts


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def validate_binding_names(names: Iterable[str]) -> None:
    """Validate dotted names while retaining legacy flat host keys.

    :param names: Binding names to inspect.
    :raises LclValidationError: If a dotted name is malformed.
    """
    for name in names:
        if "." in name:
            validate_qualified_name(name)


@guard_failure(LclValidationError, core_codes.NATIVE_841)
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


@guard_failure(LclValidationError, core_codes.NATIVE_841)
def validate_real_conflicts(names: Iterable[str]) -> None:
    """Reject strict ancestor relationships among real binding names.

    :param names: Effective real names; exact duplicates are allowed.
    :raises LclValidationError: If one real name is a strict dotted prefix of another.
    """
    unique = tuple(dict.fromkeys(names))
    selected = set(unique)
    for name in unique:
        parts = name.split(".")
        for index in range(1, len(parts)):
            ancestor = ".".join(parts[:index])
            if ancestor in selected:
                error = LclValidationError(
                    f"scoped binding conflict between {ancestor!r} and {name!r}",
                    code=core_codes.E41_SCOPED_BINDING_CONFLICT_BETWEEN_VALUE_AND_VALUE,
                )
                error.__dict__["binding_names"] = (ancestor, name)
                raise error
