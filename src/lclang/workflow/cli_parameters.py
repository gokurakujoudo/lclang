"""Derive display-only dataclass fields from explicit external workflow inputs."""

from dataclasses import MISSING, fields, is_dataclass, replace
from typing import get_origin

from lclang.cli.models import ParameterDoc
from lclang.cli.parameter_details import DerivedParameterDoc
from lclang.defaults import DefaultBinding
from lclang.utils.boxes import get_box_type
from lclang.workflow.mappings.annotations import record_annotations


def expand_record_parameters(parameters: tuple[ParameterDoc, ...]) -> tuple[ParameterDoc, ...]:
    """Add static record field descriptions without creating workflow variables.

    :param parameters: Explicit external variables, which take precedence at shared paths.
    :returns: Unique root and field descriptions in declaration traversal order.
    :raises TypeError: If annotations, field help or overlapping field types are incompatible.
    :raises ValueError: If a derived name is not a supported CLI path.
    """
    explicit = {item.name: item for item in parameters}
    output = dict(explicit)

    def visit(parent: ParameterDoc, root: str, active: frozenset[type[object]]) -> None:
        """Inspect one definite dataclass annotation without invoking its constructor.

        :param parent: Description whose fields may be expanded.
        :param root: Owning external variable name.
        :param active: Record classes already on this path, bounding recursive annotations.
        :raises TypeError: If field metadata or an overlapping annotation is incompatible.
        """
        cls = get_origin(parent.value_type) or parent.value_type
        if (
            not isinstance(cls, type)
            or not is_dataclass(cls)
            or get_box_type(parent.value_type) is not None
            or cls in active
        ):
            return
        annotations = record_annotations(parent.value_type)
        for item in fields(cls):
            if not item.init:
                continue
            name = f"{parent.name}.{item.name}"
            default = None
            if item.default is not MISSING:
                default = DefaultBinding(item.default)
            elif item.default_factory is not MISSING:
                default = DefaultBinding(factory=item.default_factory)
            description = item.metadata.get("help", "NO HELP MESSAGE PROVIDED")
            inferred: ParameterDoc = DerivedParameterDoc(
                name,
                annotations[item.name],
                parent.required and default is None,
                description,
                masked=parent.masked,
                root_name=root,
                help_default=default,
            )
            if name in explicit:
                if explicit[name].value_type != inferred.value_type:
                    raise TypeError(f"conflicting CLI field annotation: {name}")
                inferred = replace(explicit[name], masked=explicit[name].masked or parent.masked)
            output[name] = inferred
            visit(inferred, root, active | {cls})

    for parameter in parameters:
        visit(output[parameter.name], parameter.name, frozenset())
    return tuple(output.values())
