"""Typed read-only field paths rooted at workflow variables."""

from dataclasses import dataclass

from lclang.workflow.record_annotations import record_annotations
from lclang.workflow.variables import TaskVar


@dataclass(frozen=True, slots=True)
class TaskProjection[ValueT](TaskVar[ValueT]):
    """Retain a dataclass field path without creating a new binding.

    :param name: Root variable name, also used for dependency ownership.
    :param description: Root variable help text.
    :param is_masked: Root variable masking flag.
    :param value_type: Selected field annotation.
    :param root: Original variable declaration.
    :param path: Ordered dataclass field segments.
    """

    root: TaskVar[object]
    path: tuple[str, ...]


def project_field[FieldT](
    source: TaskVar[object], name: str, field_type: type[FieldT],
) -> TaskProjection[FieldT]:
    """Validate and append one declared field to a reference.

    :param source: Root variable or preceding projection.
    :param name: Direct dataclass field name.
    :param field_type: Expected exact field annotation.
    :returns: New immutable field projection.
    :raises ValueError: If the field is not declared.
    :raises TypeError: If the source or field type is incompatible.
    """
    annotations = record_annotations(source.value_type)
    if name not in annotations:
        raise ValueError(f"unknown workflow field: {source.name}.{name}")
    if annotations[name] != field_type:
        raise TypeError(f"workflow field annotation mismatch: {source.name}.{name}")
    root = source.root if isinstance(source, TaskProjection) else source
    path = (*source.path, name) if isinstance(source, TaskProjection) else (name,)
    return TaskProjection(
        root.name, root.description, root.is_masked, field_type,
        root, path,
    )


def reference_name(variable: TaskVar[object]) -> str:
    """Render a reference with its complete projected field path.

    :param variable: Root or projected workflow variable.
    :returns: Qualified diagnostic path, without a masking suffix.
    """
    return ".".join((variable.name, *variable.path)) if isinstance(
        variable, TaskProjection,
    ) else variable.name
