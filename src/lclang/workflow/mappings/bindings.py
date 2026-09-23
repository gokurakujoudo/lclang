"""Recursive workflow mapping validation, resolution, and publication."""

from dataclasses import fields, is_dataclass
from inspect import formatannotation
from typing import Any, cast, get_origin

from lclang.runtime import Frame, FrameProxy
from lclang.utils.boxes import get_box_type, unbox_value
from lclang.utils.representation import safe_repr
from lclang.workflow.mappings.records import record_type
from lclang.workflow.mappings.structure import (
    MappingNode,
    mapping_nodes,
    mapping_structure,
    validate_mapping,
)
from lclang.workflow.mappings.values import materialize_node
from lclang.workflow.projections import TaskProjection, reference_name
from lclang.workflow.variables import TaskVar


def require_mapping(value: object, field: str) -> object:
    """Accept and validate a recursive dataclass mapping.

    :param value: Candidate dataclass template or whole-record quote.
    :param field: Diagnostic label, including the mapping direction.
    :returns: Original validated declaration.
    :raises TypeError: If the mapping shape or reference contracts are invalid.
    :raises ValueError: If a template contains a cycle.
    """
    if isinstance(value, TaskVar):
        record_type(value.value_type)
    elif isinstance(value, type) or not is_dataclass(value):
        raise TypeError(f"{field} must be a dataclass instance")
    validate_mapping(value, output="output" in field)
    return value


def mapping_variables(mapping: object | None) -> tuple[TaskVar[object], ...]:
    """Find root-variable dependencies throughout one mapping.

    :param mapping: Optional mapping declaration.
    :returns: Ordered references with projections reduced to their root declarations.
    """
    if mapping is None:
        return ()
    return tuple(
        node.value.root if isinstance(node.value, TaskProjection) else node.value
        for node in mapping_nodes(mapping_structure(mapping))
        if isinstance(node.value, TaskVar)
    )


async def materialize_args(mapping: object, frame: Frame) -> object:
    """Resolve every quoted field in a recursively typed argument mapping.

    :param mapping: Argument template or whole-record quote.
    :param frame: Current task Frame.
    :returns: Materialized arguments retaining literal container references.
    :raises Exception: If structure validation or reference resolution fails.
    """
    return await materialize_node(mapping_structure(mapping), frame)


async def output_updates(node: MappingNode, output: object, frame: Frame) -> dict[str, object]:
    """Collect output bindings without mutating the destination Frame.

    :param node: Mapping structure selecting output fields.
    :param output: Returned value at this location.
    :param frame: Destination used to identify pre-existing scopes and masks.
    :returns: Complete staged binding updates.
    :raises TypeError: If a mapped record has the wrong class or a target is read-only.
    :raises ValueError: If two mapped fields publish the same normalized name.
    :raises Exception: If reading an existing target fails.
    """
    mapping = node.value
    if isinstance(mapping, TaskProjection):
        raise TypeError("workflow output projections are read-only")
    if isinstance(mapping, TaskVar):
        masked = mapping.is_masked or frame.is_masked(mapping.name)
        suffix = "!" if masked else ""
        output = unbox_value(output, mapping.value_type)
        if get_box_type(mapping.value_type) is not None:
            return {mapping.name + suffix: output}
        if is_dataclass(get_origin(mapping.value_type) or mapping.value_type):
            if type(output) is not record_type(mapping.value_type):
                raise TypeError("workflow output must match its mapping dataclass")
            current = await frame.get(mapping.name, fallback=None)
            if isinstance(current, FrameProxy):
                return {
                    f"{mapping.name}.{item.name}{suffix}": getattr(output, item.name)
                    for item in fields(cast(Any, output))
                }
        return {mapping.name + suffix: output}
    if not isinstance(mapping, type) and is_dataclass(mapping):
        if type(output) is not type(mapping):
            raise TypeError(f"{node.path}: workflow output must match its mapping dataclass")
        updates: dict[str, object] = {}
        for child in node.children:
            incoming = await output_updates(
                child, getattr(output, cast(Any, child.field).name), frame,
            )
            existing = {key.rstrip("!") for key in updates}
            if existing & {key.rstrip("!") for key in incoming}:
                raise ValueError(f"{child.path}: duplicate workflow output target")
            updates.update(incoming)
        return updates
    return {}


async def mapped_outputs(
    mapping: object | None, output: object, frame: Frame,
) -> dict[str, object]:
    """Extract the complete publication set before the caller's atomic mixin.

    :param mapping: Optional output declaration.
    :param output: Returned action or context record.
    :param frame: Destination Frame.
    :returns: Validated staged bindings, including exact-name mask markers.
    :raises Exception: If extraction or target lookup fails, without publishing values.
    """
    if mapping is None:
        return {}
    return await output_updates(mapping_structure(mapping), output, frame)


def mapping_text(mapping: object | None, output: bool) -> str:
    """Render recursive mappings with stable flattened field paths.

    :param mapping: Optional dataclass mapping or whole-record reference.
    :param output: Whether arrows describe publication.
    :returns: Compact deterministic mapping text.
    """
    if mapping is None:
        return "<none>"
    arrow = "->" if output else "<-"
    if isinstance(mapping, TaskVar):
        label = formatannotation(mapping.value_type).replace("collections.abc.", "")
        return f"{label} {arrow} ${reference_name(mapping)}{'!' if mapping.is_masked else ''}"
    parts: list[str] = []
    for node in mapping_nodes(mapping_structure(mapping)):
        if not node.path or node.children:
            continue
        value = node.value
        if isinstance(value, TaskVar):
            text = f"${reference_name(value)}{'!' if value.is_masked else ''}"
        else:
            text = "<unmapped>" if output else safe_repr(value)
        parts.append(f"{node.path} {arrow} {text}")
    return f"{type(mapping).__name__}{{{', '.join(parts)}}}"
