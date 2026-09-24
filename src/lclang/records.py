"""Public immutable values produced by LCL record displays."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from lclang.lang.lexer.tokens import TokenKind

# LCL keywords and canonical constant spellings unavailable as dotted field names.
# Unitless reserved attribute names come from record inspection methods. Excluding these exact
# names prevents user fields from shadowing the record interface.
RECORD_RESERVED_NAMES = frozenset(
    [kind.value for kind in TokenKind if kind.name.startswith("KW_")] + ["True", "False", "None"]
)


class LclRecord:
    """Expose a shallow immutable snapshot through named attributes.

    :param fields: Non-empty mapping of valid LCL field names to retained values.
    :raises TypeError: If *fields* is not a mapping or contains a non-string key.
    :raises ValueError: If no field is supplied or a name is unavailable in LCL.

    .. note::
       Field values are retained by reference. Equality and hashing ignore
       declaration order, while representation preserves it.
    """

    __slots__ = ("_fields",)

    _fields: Mapping[str, object]

    def __init__(self, fields: Mapping[str, object]) -> None:
        """Validate and detach one declaration-ordered field mapping.

        :param fields: Non-empty mapping copied before the record is published.
        :raises TypeError: If *fields* is not a mapping or has a non-string key.
        :raises ValueError: If a field name is invalid or reserved.
        """
        if not isinstance(fields, Mapping):
            raise TypeError("record fields must be a mapping")
        snapshot = dict(fields)
        if not snapshot:
            raise ValueError("record requires at least one field")
        for name in snapshot:
            if not isinstance(name, str):
                raise TypeError("record field names must be strings")
            if not name.isidentifier() or name.startswith("__") or name in RECORD_RESERVED_NAMES:
                raise ValueError(f"invalid record field name: {name!r}")
        object.__setattr__(self, "_fields", MappingProxyType(snapshot))

    def __setattr__(self, name: str, value: object) -> None:
        """Reject every field or implementation-attribute replacement.

        :param name: Attribute name requested for assignment.
        :param value: Candidate replacement value.
        :raises AttributeError: Always, because records are immutable.
        """
        del name, value
        raise AttributeError("LclRecord is immutable")

    def __delattr__(self, name: str) -> None:
        """Reject every field or implementation-attribute deletion.

        :param name: Attribute name requested for deletion.
        :raises AttributeError: Always, because records are immutable.
        """
        del name
        raise AttributeError("LclRecord is immutable")

    def __getattribute__(self, name: str) -> Any:
        """Return a field before falling back to the record's Python attributes.

        :param name: Requested Python attribute name.
        :returns: Matching field value or an implementation attribute.
        :raises AttributeError: If neither a field nor implementation attribute exists.
        """
        fields = object.__getattribute__(self, "_fields")
        if name in fields:
            return fields[name]
        if name == "_fields":
            raise AttributeError(name)
        return object.__getattribute__(self, name)

    def __repr__(self) -> str:
        """Return declaration-ordered field text.

        :returns: Stable ``LclRecord(name=value)`` representation.
        """
        fields = object.__getattribute__(self, "_fields")
        values = ", ".join(f"{name}={value!r}" for name, value in fields.items())
        return f"LclRecord({values})"

    def __eq__(self, other: object) -> bool:
        """Compare another record by field names and values without order.

        :param other: Candidate record value.
        :returns: Whether *other* has the same named values.
        """
        if not isinstance(other, LclRecord):
            return NotImplemented
        fields = object.__getattribute__(self, "_fields")
        other_fields = object.__getattribute__(other, "_fields")
        return bool(fields == other_fields)

    def __hash__(self) -> int:
        """Hash the unordered field-name/value pairs.

        :returns: Hash compatible with record equality.
        :raises TypeError: If any retained field value is unhashable.
        """
        fields = object.__getattribute__(self, "_fields")
        return hash(frozenset(fields.items()))
