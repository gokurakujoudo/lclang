"""Failure paths and value leaves built from detached LCL diagnostic records.

Defines ``build_evaluation_tree``, ``build_loading_tree``.
"""

from typing import cast

from lclang.error.diagnostic_records import EvaluationContextFrame
from lclang.error.exception_base import LclError
from lclang.error.source_excerpt import (
    render_definition_location,
    render_source_excerpt,
    render_source_location,
)
from lclang.utils.binding_mask import MASKED_VALUE
from lclang.utils.text_tree import TextTree, build_text_tree, sort_display_name
from lclang.utils.value_representation import safe_repr


def build_evaluation_tree(
    error: LclError,
    *,
    masked: bool = False,
    frames: tuple[EvaluationContextFrame, ...] | None = None,
    tail: tuple[TextTree, ...] = (),
    include_excerpt: bool = True,
) -> TextTree | None:
    """Build only the active failure branch, retaining already-read value leaves.

    :param error: Failure with immutable evaluation and source evidence.
    :param masked: Additional redaction inherited from a containing group.
    :param frames: Optional selected context suffix or common prefix.
    :param tail: Actual group-member branches below a common prefix.
    :param include_excerpt: Whether this node owns the source body.
    :returns: Outermost variable tree, or None when no language frames were captured.
    """
    selected_frames = error.evaluation_context if frames is None else frames
    branch: TextTree | None = None
    for index in range(len(selected_frames) - 1, -1, -1):
        frame = selected_frames[index]
        hidden = masked or frame.masked
        expression = MASKED_VALUE if hidden else frame.expression
        if frame.kind == "target" and frame.span.snapshot is not None and not hidden:
            snapshot = frame.span.snapshot
            start = frame.span.start.offset - snapshot.start.offset
            end = frame.span.end.offset - snapshot.start.offset
            expression = safe_repr(snapshot.text[start:end], renderer=str, max_length=None)
        location = render_definition_location(frame.span)
        children: list[TextTree] = list(tail) if branch is None else []
        for value in sorted(frame.used_values, key=lambda value: sort_display_name(value.name)):
            payload = (
                MASKED_VALUE if value.masked or hidden else (f"({value.type_name}) {value.value}")
            )
            source = value.source
            children.append((f"{value.name}: {payload} ({source})", ()))
        if branch is not None:
            children = [
                child
                for child in children
                if child[0].split(":", 1)[0] != selected_frames[index + 1].name
            ]
            children.append(branch)
        elif not hidden and include_excerpt:
            span = error.span or frame.span
            excerpt = render_source_excerpt(span)
            if excerpt:
                children.append(
                    ("Source: " + render_source_location(span) + "\n" + "\n".join(excerpt), ())
                )
        name = "using target" if frame.kind == "target" else frame.name
        if frame.callable_definition is not None and not hidden:
            definition = frame.callable_definition
            expression = "Python function " + safe_repr(definition.qualified_name, renderer=str)
            filename = safe_repr(definition.filename, renderer=str, max_length=None)
            location = f'"{filename}":{definition.line}'
        branch = (f"{name}: {expression} ({location})", tuple(children))
    if branch is None and frames is None and error.variable_stack:
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
            declaration = "\n".join(render_source_excerpt(frame.declaration_span, underline=False))
            label = (
                safe_repr(declaration or "using target", renderer=str, masked=error.masked)
                + " ("
                + render_source_location(frame.declaration_span)
                + ")"
            )
        if frame.target is not None:
            label += " -> " + safe_repr(
                frame.target, renderer=str, max_length=None, masked=error.masked
            )
        # Recursive tuple aliases need explicit context in Pyright's loop narrowing.
        descendants = cast(tuple[TextTree, ...], () if branch is None else (branch,))
        branch = (label, descendants)
    return branch
