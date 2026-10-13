"""Python exception trees with optional language-frame filtering.

Defines ``render_failure_traceback``, ``build_traceback_tree``, ``select_traceback_frames``,
``contains_traceback_frames``, ``select_traceback_nodes``.
"""

import traceback
from types import TracebackType
from typing import Literal, cast

from lclang.error.exception_base import LclError
from lclang.error.failure_summary import render_failure_summary
from lclang.utils.text_tree import TextTree, render_text_tree
from lclang.utils.value_representation import safe_repr


def select_traceback_nodes(
    tb: TracebackType | None, style: Literal["compact", "full"]
) -> tuple[TracebackType, ...]:
    """Select original traceback nodes so shared evidence can be compared by identity.

    :param tb: Original traceback, never modified.
    :param style: Compact omits lclang modules; full retains every node.
    :returns: Selected original nodes in outer-to-inner order.
    """
    selected: list[TracebackType] = []
    while tb is not None:
        module = tb.tb_frame.f_globals.get("__name__", "")
        if not (
            style == "compact"
            and isinstance(module, str)
            and (module == "lclang" or module.startswith("lclang."))
        ):
            selected.append(tb)
        tb = tb.tb_next
    return tuple(selected)


def select_traceback_frames(
    tb: TracebackType | None, style: Literal["compact", "full"]
) -> list[str]:
    """Select Python frames by their producing module identity.

    :param tb: Original traceback, never rewritten or detached from its exception.
    :param style: Compact removes all lclang frames; full retains every frame.
    :returns: Standard Python frame text in original outer-to-inner order.
    """
    selected: list[str] = []
    for node in select_traceback_nodes(tb, style):
        selected.append("".join(traceback.extract_tb(node, limit=1).format()).strip())
    return selected


def render_failure_traceback(
    error: BaseException,
    tb: TracebackType | None,
    *,
    style: Literal["compact", "full"] = "compact",
    require_frames: bool = False,
) -> str:
    """Render stack evidence with concise LCL leaves and complete native chains.

    :param error: Original failure containing cause, context and group members.
    :param tb: Traceback selected by the logging record.
    :param style: Compact module filtering or complete Python frame evidence.
    :param require_frames: Return no text when the selected tree has no Python frames.
    :returns: Exception tree without repeated complete LCL diagnostic paragraphs.
    """
    tree = build_traceback_tree(error, tb, style, set())
    if require_frames and not contains_traceback_frames(tree):
        return ""
    return "\n".join(render_text_tree(tree))


def contains_traceback_frames(tree: TextTree) -> bool:
    """Check detached evidence without re-examining any original exceptions.

    :param tree: Already built Python exception tree.
    :returns: Whether any branch contains at least one selected Python frame.
    """
    return tree[0] == "Traceback (most recent call last)" or any(
        contains_traceback_frames(child) for child in tree[1]
    )


def build_traceback_tree(
    error: BaseException,
    tb: TracebackType | None,
    style: Literal["compact", "full"],
    seen: set[int],
    *,
    masked: bool = False,
) -> TextTree:
    """Retain native relationships and report-local cycle protection.

    :param error: Exception at the current branch.
    :param tb: Original branch traceback.
    :param style: Requested Python frame policy.
    :param seen: Report-local identities already expanded.
    :param masked: Redaction inherited from the containing LCL diagnostic.
    :returns: Detached tree containing selected stack evidence and native relationships.
    """
    if isinstance(error, LclError):
        masked = masked or error.masked or any(frame.masked for frame in error.evaluation_context)
    heading = render_failure_summary(error, masked=masked)
    if not isinstance(error, LclError):
        payload = safe_repr(error, renderer=str, max_length=None, masked=masked)
        heading = f"{type(error).__name__}: {payload}"
    if id(error) in seen:
        return heading + " (exception-chain cycle or already shown)", ()
    seen.add(id(error))
    children: list[TextTree] = []
    cause, context = error.__cause__, error.__context__
    shared_stack = (
        isinstance(error, LclError)
        and cause is not None
        and select_traceback_nodes(tb, style) == select_traceback_nodes(cause.__traceback__, style)
    )
    frames = [] if shared_stack else select_traceback_frames(tb, style)
    if frames:
        children.append(
            ("Traceback (most recent call last)", tuple((frame, ()) for frame in frames))
        )
    if cause is not None:
        children.insert(
            0,
            (
                "Direct cause",
                (build_traceback_tree(cause, cause.__traceback__, style, seen, masked=masked),),
            ),
        )
    elif context is not None and not error.__suppress_context__:
        children.insert(
            0,
            (
                "During handling",
                (build_traceback_tree(context, context.__traceback__, style, seen, masked=masked),),
            ),
        )
    notes: list[TextTree] = [
        ("Context: " + safe_repr(note, renderer=str, max_length=None, masked=masked), ())
        for note in getattr(error, "__notes__", ())
    ]
    if not isinstance(error, LclError):
        children.extend(notes)
    if isinstance(error, BaseExceptionGroup):
        for index, member in enumerate(
            cast(BaseExceptionGroup[BaseException], error).exceptions, 1
        ):
            children.append(
                (
                    f"Failure {index}",
                    (
                        build_traceback_tree(
                            member, member.__traceback__, style, seen, masked=masked
                        ),
                    ),
                )
            )
    if isinstance(error, LclError):
        children[:0] = notes
    return heading, tuple(children)
