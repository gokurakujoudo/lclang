"""Dataclass mapping validation, materialization, and rendering."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from typing import Any, cast

from lclang.runtime import Frame
from lclang.utils.representation import safe_repr
from lclang.workflow.variables import TaskVar


def require_mapping(value: object, field: str) -> object:
    """Return one dataclass instance or reject it.

    :param value: Candidate mapping value.
    :param field: Diagnostic field label.
    :returns: Validated dataclass instance.
    :raises TypeError: If *value* is not a dataclass instance.
    """
    if isinstance(value, type) or not is_dataclass(value):
        raise TypeError(f"{field} must be a dataclass instance")
    return value


def mapping_variables(mapping: object | None) -> tuple[TaskVar[object], ...]:
    """Return direct TaskVar markers in dataclass field order.

    :param mapping: Optional mapping dataclass.
    :returns: Ordered direct variable markers.
    """
    if mapping is None:
        return ()
    return tuple(
        value
        for item in fields(cast(Any, mapping))
        if isinstance(value := getattr(mapping, item.name), TaskVar)
    )


async def materialize_args(mapping: object, frame: Frame) -> object:
    """Replace direct TaskVar markers with values from one Frame.

    :param mapping: Argument mapping dataclass.
    :param frame: Frame supplying referenced values.
    :returns: New dataclass instance containing real arguments.
    """
    updates: dict[str, object] = {}
    instance = cast(Any, mapping)
    for item in fields(instance):
        value = getattr(mapping, item.name)
        if isinstance(value, TaskVar):
            updates[item.name] = await frame.get(value.name)
    return cast(object, replace(instance, **updates))


def mapped_outputs(mapping: object | None, output: object) -> dict[str, object]:
    """Extract explicitly mapped fields from one returned dataclass.

    :param mapping: Optional output mapping dataclass.
    :param output: Returned action or context output.
    :returns: Frame mixin mapping, including trailing mask markers.
    :raises TypeError: If a mapped output has the wrong dataclass type.
    :raises ValueError: If two fields target the same variable.
    """
    if mapping is None:
        return {}
    if type(output) is not type(mapping):
        raise TypeError("workflow output must match its mapping dataclass")
    result: dict[str, object] = {}
    for item in fields(cast(Any, mapping)):
        variable = getattr(mapping, item.name)
        if isinstance(variable, TaskVar):
            name = variable.name + ("!" if variable.is_masked else "")
            if name in result:
                raise ValueError("duplicate workflow output target")
            result[name] = getattr(output, item.name)
    return result


def mapping_text(mapping: object | None, output: bool) -> str:
    """Render one mapping with stable field-flow notation.

    :param mapping: Optional dataclass mapping.
    :param output: Whether fields describe publication rather than arguments.
    :returns: Compact mapping text.
    """
    if mapping is None:
        return "<none>"
    parts: list[str] = []
    for item in fields(cast(Any, mapping)):
        value = getattr(mapping, item.name)
        if isinstance(value, TaskVar):
            marker = f"${value.name}{'!' if value.is_masked else ''}"
            parts.append(f"{item.name} {'->' if output else '<-'} {marker}")
        elif output:
            parts.append(f"{item.name} -> <unmapped>")
        else:
            parts.append(f"{item.name} <- {safe_repr(value)}")
    return f"{type(mapping).__name__}{{{', '.join(parts)}}}"
