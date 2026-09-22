"""Recursive mapping log rows with masking before field access."""

from dataclasses import MISSING, fields, is_dataclass
from inspect import formatannotation
from typing import Any, get_origin

from lclang.diagnostics import internal_render_value
from lclang.masking import MASKED_VALUE
from lclang.runtime import Frame
from lclang.workflow.projections import reference_name
from lclang.workflow.record_annotations import record_annotations
from lclang.workflow.variables import TaskVar


def mapping_rows(
    mapping: Any, value: Any, frame: Frame, *, output: bool,
    path: str = "", source: str = "", inherited_mask: bool = False,
    annotation: Any = None,
) -> list[tuple[str, str, str]]:
    """Build field rows after checking masks at every selected location.

    :param mapping: Dataclass template, whole reference, or absent output mapping.
    :param value: Materialized record whose unmasked fields may be read.
    :param frame: Effective task environment supplying masking metadata.
    :param output: Whether this is an output record.
    :param path: Diagnostic field prefix.
    :param source: Whole-record source path inherited by nested fields.
    :param inherited_mask: Whether a containing record is masked.
    :param annotation: Whole-record annotation, inferred when absent.
    :returns: Field path, source label, and bounded typed value for each row.
    """
    if not is_dataclass(value) or isinstance(value, type):
        return []
    marker = mapping if isinstance(mapping, TaskVar) else None
    if marker is not None:
        source = reference_name(marker)
        inherited_mask |= (
            marker.is_masked or frame.is_masked(marker.name) or frame.is_masked(source)
        )
        annotation = marker.value_type
    cls = get_origin(annotation) or annotation or type(value)
    annotations = record_annotations(annotation or cls)
    rows: list[tuple[str, str, str]] = []
    for item in sorted(fields(cls), key=lambda item: item.name):
        field_path = f"{path}.{item.name}".lstrip(".")
        field_source = f"{source}.{item.name}" if source else ""
        declared = None if mapping is None or marker is not None else getattr(mapping, item.name)
        reference = declared if isinstance(declared, TaskVar) else None
        target = source
        masked = inherited_mask or bool(field_source and frame.is_masked(field_source))
        if reference is not None:
            target = reference_name(reference)
            masked |= (
                reference.is_masked or frame.is_masked(reference.name) or frame.is_masked(target)
            )
        if target:
            label = f"[{target}]"
        elif output:
            label = "unused"
        else:
            uses_default = item.default is not MISSING and declared == item.default
            label = "default" if uses_default else "literal"
        expected = annotations[item.name]
        if masked:
            rendered = f"({formatannotation(expected)}) {MASKED_VALUE}"
        else:
            current = getattr(value, item.name)
            if is_dataclass(current) and not isinstance(current, type):
                rows.extend(mapping_rows(
                    reference or declared, current, frame, output=output, path=field_path,
                    source=field_source, annotation=expected,
                ))
                continue
            rendered = internal_render_value(current)
        rows.append((field_path, label, rendered))
    return rows
