"""Recursive argument materialization and typed reference resolution."""

from dataclasses import MISSING, fields, is_dataclass, replace
from types import UnionType
from typing import Any, Union, cast, get_args, get_origin

from lclang.runtime import Frame, FrameProxy
from lclang.utils.boxes import box_value, get_box_type
from lclang.workflow.mappings.annotations import record_annotations
from lclang.workflow.mappings.records import can_construct_record, record_type
from lclang.workflow.mappings.structure import MappingNode
from lclang.workflow.projections import TaskProjection, reference_name
from lclang.workflow.variables import TaskVar


def matches_annotation(value: object, annotation: Any) -> bool:
    """Check a projected value's outer type without traversing containers.

    :param value: Value obtained from a field projection.
    :param annotation: Declared projected annotation.
    :returns: Whether its outer runtime shape matches the declared type.
    """
    if annotation in (Any, object):
        return True
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(matches_annotation(value, item) for item in get_args(annotation))
    cls = origin or annotation
    return not isinstance(cls, type) or isinstance(value, cls)


async def materialize_record(value: object, annotation: Any) -> object:
    """Convert a scope into a recursively typed record, preserving concrete records.

    :param value: Referenced record or scope proxy.
    :param annotation: Concrete or generic dataclass annotation.
    :returns: Existing concrete record or a newly constructed typed record.
    :raises TypeError: If the record class differs or required fields are missing.
    :raises Exception: If a scope field cannot be evaluated.
    """
    cls = record_type(annotation)
    if isinstance(value, FrameProxy):
        annotations = record_annotations(annotation)
        available = set(await value.field_names())
        updates: dict[str, object] = {}
        for item in fields(cls):
            if item.init and item.name in available:
                current = await value.get(item.name)
                expected = annotations[item.name]
                if get_box_type(expected) is None and is_dataclass(
                    get_origin(expected) or expected,
                ):
                    current = await materialize_record(current, expected)
                updates[item.name] = current
        return cls(**updates)
    if type(value) is not cls:
        raise TypeError("workflow argument must match its mapping dataclass")
    return value


async def resolve_reference(variable: TaskVar[object], frame: Frame) -> object:
    """Resolve one root value and optionally read its declared dataclass path.

    :param variable: Root variable or read-only projection.
    :param frame: Current task lookup environment.
    :returns: Concrete referenced value with record proxies materialized.
    :raises TypeError: If a projected value has the wrong type or is null.
    :raises Exception: If lookup, record conversion or projected type checks fail.
    """
    root = variable.root if isinstance(variable, TaskProjection) else variable
    if not frame.has(root.name) and can_construct_record(root.value_type):
        value = record_type(root.value_type)()
    else:
        value = box_value(await frame.get(root.name), root.value_type)
    if get_box_type(root.value_type) is None and is_dataclass(
        get_origin(root.value_type) or root.value_type,
    ):
        value = await materialize_record(value, root.value_type)
    if isinstance(variable, TaskProjection):
        annotation = root.value_type
        for name in variable.path:
            expected = record_annotations(annotation)[name]
            value = box_value(getattr(value, name), expected)
            if not matches_annotation(value, expected):
                detail = "null value" if value is None else "type mismatch"
                raise TypeError(f"workflow field {detail}: {reference_name(variable)}")
            annotation = expected
    return value


async def materialize_node(node: MappingNode, frame: Frame) -> object:
    """Build one mapping node while preserving non-record literal identity.

    :param node: Validated mapping structure.
    :param frame: Frame supplying quote values.
    :returns: Materialized value or detached dataclass template.
    :raises Exception: If a quote cannot be resolved, with a mapping-path note.
    """
    value: object = node.value
    if isinstance(value, TaskVar):
        variable = cast(TaskVar[object], value)
        try:
            if not frame.has(variable.name) and node.field is not None:
                if node.field.default is not MISSING:
                    return node.field.default
                if node.field.default_factory is not MISSING:
                    return node.field.default_factory()
            return await resolve_reference(variable, frame)
        except Exception as error:
            error.add_note(
                f"workflow mapping {node.path or '<record>'} <- " f"{reference_name(variable)}"
            )
            raise
    if not isinstance(node.value, type) and is_dataclass(node.value):
        updates = {
            child.field.name: await materialize_node(child, frame)
            for child in node.children
            if child.field is not None and child.field.init
        }
        return replace(cast(Any, node.value), **updates)
    return node.value
