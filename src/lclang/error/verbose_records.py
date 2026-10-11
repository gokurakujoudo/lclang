"""Readable DEBUG records with immutable producer-side context.

Defines ``describe_verbose_context``, ``emit_verbose_record``.
"""

import asyncio

from lclang.error.using_diagnostics import ACTIVE_USING_DIAGNOSTICS, describe_using_subject
from lclang.error.verbose_context import ACTIVE_VERBOSE_CONTEXT, ACTIVE_VERBOSE_LOGGER
from lclang.error.verbose_loading import ACTIVE_LOADING_ROUTE
from lclang.utils.text_tree import TextTree, render_text_tree
from lclang.utils.value_representation import safe_repr


def describe_verbose_context(*, human: bool = False) -> tuple[tuple[str, str], ...]:
    """Detach the context already obtained by execution and lookup.

    :param human: Translate generated names only for displayed details.
    :returns: Immutable text field pairs, without Frames or host objects.
    """
    context = ACTIVE_VERBOSE_CONTEXT.get()
    fields: list[tuple[str, str]] = []
    if context.evaluation_id is not None:
        fields.append(("Evaluation", context.evaluation_id))
    if context.request_path:
        fields.append(
            (
                "Request",
                " -> ".join(
                    describe_using_subject(name) if human else name for name in context.request_path
                ),
            )
        )
    if context.requester is not None:
        frames = f'requested from "{context.requester}"'
        if context.owner is not None:
            frames += f'; defined in "{context.owner}"'
        fields.append(("Frames", frames))
    if context.lookup_path:
        fields.append(("Lookup path", " -> ".join(context.lookup_path)))
    if context.execution is not None:
        fields.append(("Execution", context.execution))
    route = ACTIVE_LOADING_ROUTE.get()
    if route:
        from lclang.error.source_excerpt import render_source_location

        fields.append(
            (
                "Loading route",
                " -> ".join(
                    (
                        render_source_location(frame.declaration_span)
                        if frame.declaration_span is not None
                        else str(frame.origin.name)
                    )
                    for frame in route
                ),
            )
        )
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    if task is not None:
        fields.append(("Task", task.get_name()))
    using = ACTIVE_USING_DIAGNOSTICS.get()
    if human and using is not None:
        fields = [
            (
                name,
                (
                    value.replace('"' + using.target_frame + '"', '"using target"').replace(
                        '"' + using.context_frame + '"', '"using context"'
                    )
                    if name == "Frames"
                    else (
                        value.replace(using.target_frame, "using target")
                        if name == "Lookup path"
                        else value
                    )
                ),
            )
            for name, value in fields
        ]
    return tuple((name, safe_repr(value, renderer=str, max_length=None)) for name, value in fields)


def emit_verbose_record(
    stage: str,
    heading: str,
    *,
    details: tuple[tuple[str, str], ...] = (),
    failure_id: str | None = None,
    tree: TextTree | None = None,
    evaluation_id: str | None = None,
    context_details: tuple[tuple[str, str], ...] = (),
    show_tree: bool = True,
) -> None:
    """Send a readable diagnostic through the borrowed logger.

    :param stage: Stable machine-readable stage for external filters.
    :param heading: Short English description of the actual operation.
    :param details: Already-protected text details shown in fixed order.
    :param failure_id: Original failure identifier when the event refers to an error.
    :param tree: Optional already-protected detached tree for display consumers.
    :param evaluation_id: Explicit root correlation when its evaluation scope has ended.
    :param context_details: Additional protected operation evidence retained as record metadata.
    :param show_tree: Whether to print the tree as well as retaining its snapshot.
    """
    logger = ACTIVE_VERBOSE_LOGGER.get()
    if logger is None or not logger.isEnabledFor(10):
        return
    context = describe_verbose_context() + context_details
    message = "\n".join(
        (
            safe_repr(heading, renderer=str, max_length=None),
            *(
                f"  {name}: {safe_repr(value, renderer=str, max_length=None)}"
                for name, value in details
            ),
        )
    )
    if tree is not None and show_tree:
        message += "\n" + "\n".join(render_text_tree(tree))
    logger.debug(
        "%s",
        message,
        stacklevel=3,
        extra={
            "lclang_verbose": True,
            "lclang_stage": stage,
            "lclang_evaluation_id": evaluation_id or ACTIVE_VERBOSE_CONTEXT.get().evaluation_id,
            "lclang_failure_id": failure_id,
            "lclang_context": context,
            "lclang_tree": tree,
        },
    )
