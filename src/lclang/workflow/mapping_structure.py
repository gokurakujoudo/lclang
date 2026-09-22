"""Shared recursive structure for workflow mapping consumers."""

from collections.abc import Iterator
from dataclasses import Field, dataclass, fields, is_dataclass
from typing import Any

from lclang.workflow.projections import TaskProjection
from lclang.workflow.record_annotations import record_annotations
from lclang.workflow.record_types import mapping_annotation
from lclang.workflow.variables import TaskVar


@dataclass(frozen=True, slots=True)
class MappingNode:
    """Describe one mapping location without copying its retained values.

    :param value: Literal, dataclass template, or quote marker.
    :param path: Dot-connected dataclass field path.
    :param annotation: Declared field or root annotation.
    :param children: Ordered direct dataclass fields.
    :param field: Constructor metadata, absent at the mapping root.
    """

    value: Any
    path: str
    annotation: Any
    children: tuple[MappingNode, ...] = ()
    field: Field[Any] | None = None


def mapping_structure(
    value: object, path: str = "", annotation: Any = None,
    active: frozenset[int] = frozenset(), field: Field[Any] | None = None,
) -> MappingNode:
    """Build an acyclic field tree shared by evaluation and diagnostics.

    :param value: Mapping or one retained field value.
    :param path: Diagnostic path of this node.
    :param annotation: Expected field annotation, inferred at the root.
    :param active: Dataclass identities on the current recursion path.
    :param field: Optional dataclass constructor metadata.
    :returns: Detached structure retaining literal values by reference.
    :raises ValueError: If a dataclass template contains a cycle.
    :raises TypeError: If a quote contradicts its declared field annotation.
    """
    expected = mapping_annotation(value) if annotation is None else annotation
    if isinstance(value, TaskVar):
        if annotation not in (None, Any, object) and annotation != value.value_type:
            raise TypeError(f"{path}: workflow reference annotation mismatch for {value.name}")
        return MappingNode(value, path, expected, field=field)
    children: tuple[MappingNode, ...] = ()
    if not isinstance(value, type) and is_dataclass(value):
        if id(value) in active:
            raise ValueError(f"{path}: cyclic workflow dataclass mapping")
        declared = mapping_annotation(value) if annotation in (None, Any, object) else annotation
        annotations = record_annotations(declared)
        children = tuple(
            mapping_structure(
                getattr(value, item.name), f"{path}.{item.name}".lstrip("."),
                annotations[item.name], active | {id(value)}, item,
            )
            for item in fields(value)
        )
    return MappingNode(value, path, expected, children, field)


def mapping_nodes(node: MappingNode) -> Iterator[MappingNode]:
    """Walk a mapping structure in declaration order, including record nodes.

    :param node: Root of the requested structure.
    :returns: Preorder iterator of structural locations.
    """
    yield node
    for child in node.children:
        yield from mapping_nodes(child)


def validate_mapping(value: object, *, output: bool) -> None:
    """Validate directional marker constraints throughout a mapping.

    :param value: Dataclass mapping or whole-record quote.
    :param output: Whether the mapping publishes returned values.
    :raises TypeError: If a projection is used as an output or a quote cannot initialize.
    :raises ValueError: If the structure contains a cycle.
    """
    for node in mapping_nodes(mapping_structure(value)):
        if output and isinstance(node.value, TaskProjection):
            raise TypeError(f"{node.path}: workflow output projections are read-only")
        if (
            not output and isinstance(node.value, TaskVar)
            and node.field is not None and not node.field.init
        ):
            raise TypeError(f"{node.path}: input quote requires an init field")
