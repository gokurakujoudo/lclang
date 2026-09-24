"""Dataclass annotations with generic field specialization."""

from dataclasses import fields, is_dataclass
from functools import reduce
from types import UnionType
from typing import Any, Union, cast, get_args, get_origin, get_type_hints


def specialize(annotation: Any, substitutions: dict[object, object]) -> Any:
    """Substitute generic parameters throughout a field annotation.

    :param annotation: Field annotation or one nested type argument.
    :param substitutions: Declared type parameters and their concrete arguments.
    :returns: Annotation with available parameters replaced.
    """
    if not substitutions:
        return annotation
    if isinstance(annotation, list):
        return [specialize(item, substitutions) for item in cast(list[object], annotation)]
    if annotation in substitutions:
        return substitutions[annotation]
    arguments = get_args(annotation)
    if not arguments:
        return annotation
    resolved = tuple(specialize(item, substitutions) for item in arguments)
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return reduce(lambda left, right: left | right, resolved)
    return annotation.copy_with(resolved) if hasattr(annotation, "copy_with") else origin[resolved]


def record_annotations(annotation: object) -> dict[str, Any]:
    """Resolve annotated dataclass fields, including generic substitutions.

    :param annotation: Concrete or parameterized dataclass annotation.
    :returns: Field names with specialized Python annotations.
    :raises TypeError: If the annotation is not a dataclass or cannot be resolved.
    """
    cls = get_origin(annotation) or annotation
    if not isinstance(cls, type) or not is_dataclass(cls):
        raise TypeError("workflow record type must be a dataclass")
    try:
        hints = get_type_hints(cls)
    except Exception as error:
        raise TypeError("workflow dataclass annotations cannot be resolved") from error
    parameters: tuple[object, ...] = getattr(cls, "__type_params__", ()) or getattr(
        cls, "__parameters__", ()
    )
    substitutions: dict[object, object] = dict(zip(parameters, get_args(annotation), strict=False))
    return {item.name: specialize(hints[item.name], substitutions) for item in fields(cls)}
