"""Uniform failure trees built only from detached diagnostic evidence.

Defines ``render_error``, ``render_failure``, ``build_failure_tree``, ``select_error_action``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from lclang.error.exception_base import LclError
from lclang.error.failure_summary import describe_failure_reason, render_failure_summary

if TYPE_CHECKING:
    from lclang.utils.text_tree import TextTree


def render_error(error: LclError) -> str:
    """Render the complete failure path and inline reason from frozen records.

    :param error: Structured failure with detached source and value evidence.
    :returns: English diagnostic tree without a terminal newline.
    """
    return render_failure(error, action="")


def render_failure(error: BaseException, *, action: str) -> str:
    """Render one application report with native chains and every group member.

    :param error: Original exception, whose propagation state remains unchanged.
    :param action: Operation label for failures without language evidence.
    :returns: Shared multiline diagnostic with inline code reasons.
    """
    from lclang.utils.text_tree import render_text_tree

    return "\n".join(render_text_tree(build_failure_tree(error, action, set())))


def build_failure_tree(
    error: BaseException,
    action: str,
    seen: set[int | str],
    *,
    masked: bool = False,
    frozen_reason: str | None = None,
) -> TextTree:
    """Build a report-local tree without expanding the same LCL failure twice.

    :param error: Original exception on this branch.
    :param action: Operation label for an evidence-free error.
    :param seen: Report-local identities already expanded, including sibling members.
    :param masked: Redaction inherited from the parent diagnostic.
    :param frozen_reason: Owner-captured native cause text, avoiding another native str call.
    :returns: Detached protected text and ordered child trees.
    """
    from lclang.error.codes.e0_general_error_code import GeneralErrorCode
    from lclang.error.diagnostic_tree import build_evaluation_tree, build_loading_tree
    from lclang.error.native_wrap import is_ordinary_failure
    from lclang.error.source_excerpt import render_source_excerpt, render_source_location
    from lclang.utils.binding_mask import MASKED_VALUE
    from lclang.utils.value_representation import safe_repr

    key = error.verbose_failure_id if isinstance(error, LclError) else None
    identity: int | str = key or id(error)
    if identity in seen:
        return render_failure_summary(error, masked=masked) + " (already shown)", ()
    seen.add(identity)
    children: list[TextTree] = []
    if isinstance(error, LclError):
        masked = masked or error.masked or any(frame.masked for frame in error.evaluation_context)
        if (
            error.native_cause is None
            and error.__cause__ is not None
            and not isinstance(error.__cause__, LclError)
        ):
            error.freeze_native_cause(error.__cause__)
        reason = describe_failure_reason(error, masked=masked, max_length=None)
        loading = build_loading_tree(error)
        evaluation = build_evaluation_tree(error, masked=masked)
        if loading is not None:
            action = f'loading config file "{error.config_stack[0].origin.name}"'
            children.append(("Loading route", (loading,)))
        elif evaluation is not None:
            action = "evaluating " + evaluation[0].split(":", 1)[0]
        else:
            selected = select_error_action(error.default_code) or select_error_action(error.code)
            action = action or selected.removeprefix(" in ")
        if evaluation is not None:
            children.append(evaluation)
        elif error.span is not None:
            excerpt = [MASKED_VALUE] if masked else render_source_excerpt(error.span)
            children.append(
                ("Source: " + render_source_location(error.span) + "\n" + "\n".join(excerpt), ())
            )
        identity_text = "" if key is None else f" (failure {key})"
        operation = " in " + action if action else ""
        heading = f"Error{operation} [{error.code}: {reason}]{identity_text}"
        if (
            error.native_cause is not None
            and error.message not in {reason, error.native_cause}
            and not masked
        ):
            children.append(
                ("Operation: " + safe_repr(error.message, renderer=str, max_length=None), ())
            )
    else:
        reason = (
            describe_failure_reason(error, masked=masked, max_length=None)
            if frozen_reason is None
            else safe_repr(frozen_reason, renderer=str, max_length=None, masked=masked)
        )
        code = (
            f" [{GeneralErrorCode.E22_NATIVE_EXCEPTION_DIAGNOSTIC}: {reason}]"
            if is_ordinary_failure(error)
            else ""
        )
        heading = (
            f"Error in {action}{code}: {type(error).__name__}: {reason}"
            if frozen_reason is None
            else reason
        )
    for note in getattr(error, "__notes__", ()):
        children.append(
            ("Context: " + safe_repr(note, renderer=str, max_length=None, masked=masked), ())
        )
    cause = error.__cause__
    context = error.__context__
    if cause is not None:
        captured = (
            error.native_cause
            if isinstance(error, LclError) and not isinstance(cause, LclError)
            else None
        )
        children.insert(
            0,
            (
                "Cause",
                (
                    build_failure_tree(
                        cause, "handling cause", seen, masked=masked, frozen_reason=captured
                    ),
                ),
            ),
        )
    elif context is not None and not error.__suppress_context__:
        children.insert(
            0,
            (
                "During handling",
                (build_failure_tree(context, "handling context", seen, masked=masked),),
            ),
        )
    if isinstance(error, BaseExceptionGroup):
        for index, member in enumerate(
            cast(BaseExceptionGroup[BaseException], error).exceptions, 1
        ):
            children.append(
                (
                    f"Failure {index}",
                    (build_failure_tree(member, "handling failure", seen, masked=masked),),
                )
            )
    return heading, tuple(children)


def select_error_action(code: str) -> str:
    """Choose the default stage for errors lacking active operation records.

    :param code: Stable structured error code.
    :returns: Optional English action phrase, including its leading separator.
    """
    if code.startswith(("LCL11", "LCL12", "LCL31")) or code == "LCL100000":
        return " in parsing source"
    if code == "LCL230000":
        return " in resolving a variable"
    if code.startswith(("LCL13", "LCL2")):
        return " in evaluating an expression"
    if code.startswith("LCL3"):
        return " in loading configuration"
    if code.startswith("LCL4"):
        return " in command-line usage"
    if code.startswith("LCL5"):
        return " in executing a workflow"
    if code.startswith("LCL6"):
        return " in logging"
    if code.startswith("LCL7"):
        return " in a utility operation"
    if code.startswith("LCL9"):
        return " in a standard-library operation"
    return ""
