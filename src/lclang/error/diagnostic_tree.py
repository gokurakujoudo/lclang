"""Failure paths and value leaves built from detached LCL diagnostic records.

Defines ``build_evaluation_tree``, ``build_loading_tree``.
"""

from typing import cast

from lclang.error.exception_base import LclError
from lclang.error.source_excerpt import (
    render_definition_location,
    render_source_excerpt,
    render_source_location,
)
from lclang.utils.binding_mask import MASKED_VALUE
from lclang.utils.text_tree import TextTree, build_text_tree, sort_display_name
from lclang.utils.value_representation import safe_repr


def build_evaluation_tree(error: LclError, *, masked: bool = False) -> TextTree | None:
    """Build only the active failure branch, retaining already-read value leaves.

    :param error: Failure with immutable evaluation and source evidence.
    :param masked: Additional redaction inherited from a containing group.
    :returns: Outermost variable tree, or None when no language frames were captured.
    """
    frames = tuple(frame for frame in error.evaluation_context if frame.kind != "target")
    branch: TextTree | None = None
    for index in range(len(frames) - 1, -1, -1):
        frame = frames[index]
        hidden = masked or frame.masked
        expression = MASKED_VALUE if hidden else frame.expression
        location = render_definition_location(frame.span)
        children: list[TextTree] = []
        for value in sorted(frame.used_values, key=lambda value: sort_display_name(value.name)):
            payload = (
                MASKED_VALUE if value.masked or hidden else (f"({value.type_name}) {value.value}")
            )
            source = value.source
            children.append((f"{value.name}: {payload} ({source})", ()))
        if branch is not None:
            children = [
                child for child in children if child[0].split(":", 1)[0] != frames[index + 1].name
            ]
            children.append(branch)
        elif not hidden:
            span = error.span or frame.span
            excerpt = render_source_excerpt(span)
            if excerpt:
                children.append(
                    ("Source: " + render_source_location(span) + "\n" + "\n".join(excerpt), ())
                )
        branch = (f"{frame.name}: {expression} ({location})", tuple(children))
    if branch is None and error.variable_stack:
        for name in reversed(error.variable_stack):
            descendants: tuple[TextTree, ...] = () if branch is None else (branch,)
            if branch is None and error.span is not None:
                excerpt = [MASKED_VALUE] if masked else render_source_excerpt(error.span)
                descendants = (
                    (
                        "Source: " + render_source_location(error.span) + "\n" + "\n".join(excerpt),
                        (),
                    ),
                )
            branch = build_text_tree(name + ": <expression unavailable>", descendants)
    return branch


def build_loading_tree(error: LclError) -> TextTree | None:
    """Build actual source introductions without reading any configuration files.

    :param error: Failure retaining its outer-to-inner loading route.
    :returns: Nested introduction tree, or None when no loading evidence exists.
    """
    branch: TextTree | None = None
    for frame in reversed(error.config_stack):
        label = safe_repr(frame.origin.name, renderer=str, max_length=None)
        if frame.declaration_span is not None:
            label += " (" + render_source_location(frame.declaration_span) + ")"
            declaration = "\n".join(render_source_excerpt(frame.declaration_span, underline=False))
            if declaration:
                label += ": " + safe_repr(declaration, renderer=str, masked=error.masked)
        if frame.target is not None:
            label += " -> " + safe_repr(
                frame.target, renderer=str, max_length=None, masked=error.masked
            )
        # Recursive tuple aliases need explicit context in Pyright's loop narrowing.
        descendants = cast(tuple[TextTree, ...], () if branch is None else (branch,))
        branch = (label, descendants)
    return branch
