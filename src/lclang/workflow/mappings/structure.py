"""Shared recursive structure for workflow mapping consumers."""

from collections.abc import Iterator
from dataclasses import Field, dataclass, fields, is_dataclass
from typing import Any

from lclang.error import LclWorkflowError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.workflow import Code as workflow_codes
from lclang.workflow.mappings.annotations import record_annotations
from lclang.workflow.mappings.records import mapping_annotation
from lclang.workflow.projections import TaskProjection
from lclang.workflow.variables import TaskVar


@guard_constructor(LclValidationError, workflow_codes.NATIVE_521)
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


@guard_failure(LclWorkflowError, workflow_codes.NATIVE_521)
def mapping_structure(
    value: object,
    path: str = "",
    annotation: Any = None,
    active: frozenset[int] = frozenset(),
    field: Field[Any] | None = None,
) -> MappingNode:
    """Build an acyclic field tree shared by evaluation and diagnostics.

    :param value: Mapping or one retained field value.
    :param path: Diagnostic path of this node.
    :param annotation: Expected field annotation, inferred at the root.
    :param active: Dataclass identities on the current recursion path.
    :param field: Optional dataclass constructor metadata.
    :returns: Detached structure retaining literal values by reference.
    :raises LclValidationError: If a dataclass template contains a cycle.
    :raises LclValidationError: If a quote contradicts its declared field annotation.
    """
    expected = mapping_annotation(value) if annotation is None else annotation
    if isinstance(value, TaskVar):
        if annotation not in (None, Any, object) and annotation != value.value_type:
            raise LclValidationError(
                f"{path}: workflow reference annotation mismatch for {value.name}",
                code=workflow_codes.E21_VALUE_WORKFLOW_REFERENCE_ANNOTATION_MISMATCH_FOR_VALUE,
            )
        return MappingNode(value, path, expected, field=field)
    children: tuple[MappingNode, ...] = ()
    if not isinstance(value, type) and is_dataclass(value):
        if id(value) in active:
            raise LclValidationError(
                f"{path}: cyclic workflow dataclass mapping",
                code=workflow_codes.E21_VALUE_CYCLIC_WORKFLOW_DATACLASS_MAPPING,
            )
        declared = mapping_annotation(value) if annotation in (None, Any, object) else annotation
        annotations = record_annotations(declared)
        children = tuple(
            mapping_structure(
                getattr(value, item.name),
                f"{path}.{item.name}".lstrip("."),
                annotations[item.name],
                active | {id(value)},
                item,
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


@guard_failure(LclValidationError, workflow_codes.NATIVE_521)
def validate_mapping(value: object, *, output: bool) -> None:
    """Validate directional marker constraints throughout a mapping.

    :param value: Dataclass mapping or whole-record quote.
    :param output: Whether the mapping publishes returned values.
    :raises LclValidationError: If a projection is used as an output or a quote cannot initialize.
    :raises LclValidationError: If the structure contains a cycle.
    """
    for node in mapping_nodes(mapping_structure(value)):
        if output and isinstance(node.value, TaskProjection):
            raise LclValidationError(
                f"{node.path}: workflow output projections are read-only",
                code=workflow_codes.E21_VALUE_WORKFLOW_OUTPUT_PROJECTIONS_ARE_READ_ONLY,
            )
        if (
            not output
            and isinstance(node.value, TaskVar)
            and node.field is not None
            and not node.field.init
        ):
            raise LclValidationError(
                f"{node.path}: input quote requires an init field",
                code=workflow_codes.E21_VALUE_INPUT_QUOTE_REQUIRES_AN_INIT_FIELD,
            )
