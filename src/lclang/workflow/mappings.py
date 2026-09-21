"""Dataclass mapping validation, materialization, and rendering."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from inspect import formatannotation
from typing import Any, cast

from lclang.runtime import Frame, FrameProxy
from lclang.utils.representation import safe_repr
from lclang.workflow.record_types import record_type
from lclang.workflow.variables import TaskVar


def require_mapping(value: object, field: str) -> object:
    """Accept a dataclass instance or a variable declaring a dataclass type.

    :param value: Candidate mapping value.
    :param field: Diagnostic field label.
    :returns: Validated dataclass instance.
    :raises TypeError: If *value* is not a dataclass mapping or record variable.
    """
    if isinstance(value, TaskVar):
        record_type(value.value_type)
    elif isinstance(value, type) or not is_dataclass(value):
        raise TypeError(f"{field} must be a dataclass instance")
    return value


def mapping_variables(mapping: object | None) -> tuple[TaskVar[object], ...]:
    """Return a whole-record marker or direct markers in dataclass field order.

    :param mapping: Optional mapping dataclass or whole-record variable.
    :returns: Ordered direct variable markers.
    """
    if mapping is None:
        return ()
    if isinstance(mapping, TaskVar):
        return (mapping,)
    return tuple(
        value
        for item in fields(cast(Any, mapping))
        if isinstance(value := getattr(mapping, item.name), TaskVar)
    )


async def materialize_args(mapping: object, frame: Frame) -> object:
    """Replace direct TaskVar markers with values from one Frame.

    :param mapping: Argument mapping dataclass or whole-record variable.
    :param frame: Frame supplying referenced values.
    :returns: Stored whole record or a materialized dataclass with resolved fields.
    :raises TypeError: If a whole variable resolves to the wrong record class.
    """
    if isinstance(mapping, TaskVar):
        cls = record_type(mapping.value_type)
        value = await frame.get(mapping.name)
        if isinstance(value, FrameProxy):
            value = await value.as_record(cls)
        if type(value) is not cls:
            raise TypeError("workflow argument must match its mapping dataclass")
        return value
    updates: dict[str, object] = {}
    instance = cast(Any, mapping)
    for item in fields(instance):
        value = getattr(mapping, item.name)
        if isinstance(value, TaskVar):
            updates[item.name] = await frame.get(value.name)
    return cast(object, replace(instance, **updates))


async def mapped_outputs(
    mapping: object | None, output: object, frame: Frame,
) -> dict[str, object]:
    """Extract explicitly mapped fields from one returned dataclass.

    :param mapping: Optional output dataclass mapping or whole-record variable.
    :param output: Returned action or context output.
    :param frame: Destination Frame used to recognize an existing scope proxy.
    :returns: Frame mixin mapping, including trailing mask markers.
    :raises TypeError: If a mapped output has the wrong dataclass type.
    :raises ValueError: If two fields target the same variable.
    :raises Exception: If resolving an existing whole-record target fails.
    """
    if mapping is None:
        return {}
    if isinstance(mapping, TaskVar):
        if type(output) is not record_type(mapping.value_type):
            raise TypeError("workflow output must match its mapping dataclass")
        masked = mapping.is_masked or frame.is_masked(mapping.name)
        suffix = "!" if masked else ""
        current = await frame.get(mapping.name, fallback=None)
        if isinstance(current, FrameProxy):
            return {
                f"{mapping.name}.{item.name}{suffix}": getattr(output, item.name)
                for item in fields(cast(Any, output))
            }
        return {mapping.name + suffix: output}
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
    if isinstance(mapping, TaskVar):
        label = formatannotation(mapping.value_type).replace("collections.abc.", "")
        marker = f"${mapping.name}{'!' if mapping.is_masked else ''}"
        return f"{label} {'->' if output else '<-'} {marker}"
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
