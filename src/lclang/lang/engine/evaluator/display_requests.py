"""Actual request and call boundaries for transient runtime display trees.

Defines ``scope_display_request``, ``scope_display_expression``, ``record_display_value``,
``finish_display_request``.
"""

from collections.abc import Generator
from contextlib import contextmanager

from lclang.error.diagnostic_rendering import build_failure_tree
from lclang.error.failure_summary import render_failure_summary
from lclang.error.mask_scope import ACTIVE_MASKED_VALUE
from lclang.error.native_wrap import is_ordinary_failure
from lclang.error.source_excerpt import render_definition_location, render_source_excerpt
from lclang.error.using_diagnostics import ACTIVE_USING_DIAGNOSTICS
from lclang.error.verbose_context import (
    ACTIVE_VERBOSE_CONTEXT,
    allocate_verbose_id,
    is_verbose_enabled,
)
from lclang.error.verbose_propagation import scope_verbose_failure_batch
from lclang.error.verbose_records import emit_verbose_record
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.evaluator.display_capture import (
    ACTIVE_DISPLAY_CAPTURE,
    ACTIVE_DISPLAY_REQUEST,
    DisplayRequest,
    render_display_value,
)
from lclang.lang.engine.evaluator.evaluation_journal import ACTIVE_TARGET_EXPRESSION
from lclang.lang.engine.printer import to_source
from lclang.utils.value_representation import safe_repr


@contextmanager
def scope_display_request(
    name: str, node: LclAstNode | None, execution: str, *, masked: bool = False
) -> Generator[DisplayRequest | None]:
    """Collect a binding request only when a current consumer needs its display.

    :param name: Actual selected name, without another lookup.
    :param node: Already-selected syntax, omitted for non-definition inputs.
    :param execution: Actual pre-await source, including cached or shared work.
    :param masked: Exact binding mask obtained during ordinary resolution.
    :returns: Temporary builder, or None when display work is disabled.
    """
    parent = ACTIVE_DISPLAY_REQUEST.get()
    if not is_verbose_enabled() and ACTIVE_DISPLAY_CAPTURE.get() is None:
        yield None
        return
    masked = masked or ACTIVE_MASKED_VALUE.get() or (parent is not None and parent.masked)
    request = DisplayRequest(name, name + ": <pending>", execution, masked=masked)
    if node is not None and node is ACTIVE_TARGET_EXPRESSION.get():
        request.kind = "target"
    if node is not None and execution == "new evaluation":
        expression = safe_repr(
            node, renderer=lambda value: to_source(node), max_length=None, masked=masked
        )
        label = "using target" if request.kind == "target" else name
        request.label = f"{label}: {expression} ({render_definition_location(node.span)})"
    if parent is not None:
        parent.children.append(request)
    elif (capture := ACTIVE_DISPLAY_CAPTURE.get()) is not None:
        capture.tree = capture.result = None
    token = ACTIVE_DISPLAY_REQUEST.set(request)
    try:
        with scope_verbose_failure_batch(name):
            yield request
    except BaseException as error:
        if is_ordinary_failure(error) and (
            is_verbose_enabled() or ACTIVE_DISPLAY_CAPTURE.get() is not None
        ):
            request.label = f"{name}: {render_failure_summary(error, masked=masked)} ({execution})"
            capture = ACTIVE_DISPLAY_CAPTURE.get()
            if parent is None and capture is not None:
                capture.result = None
                capture.tree = (
                    build_failure_tree(error, "evaluating " + name, set(), masked=masked)
                    if execution == "new evaluation"
                    else request.freeze()
                )
        raise
    else:
        if parent is None:
            finish_display_request(request)
    finally:
        ACTIVE_DISPLAY_REQUEST.reset(token)


@contextmanager
def scope_display_expression(
    name: str, node: LclAstNode, *, call: bool = False
) -> Generator[DisplayRequest | None]:
    """Nest actual function invocations and correlate expression boundaries.

    :param name: Active definition or lexical function label.
    :param node: Actual body being evaluated.
    :param call: Whether this scope represents a function invocation.
    :returns: Current expression builder, or None when no display is requested.
    """
    if not is_verbose_enabled() and ACTIVE_DISPLAY_CAPTURE.get() is None:
        yield None
        return
    parent = ACTIVE_DISPLAY_REQUEST.get()
    if parent is None:
        with scope_display_request(name, node, "new evaluation") as request:
            if request is not None:
                request.evaluation_id = (
                    ACTIVE_VERBOSE_CONTEXT.get().evaluation_id or allocate_verbose_id("E")
                )
            yield request
        return
    if not call:
        parent.evaluation_id = ACTIVE_VERBOSE_CONTEXT.get().evaluation_id or allocate_verbose_id(
            "E"
        )
        yield parent
        return
    with scope_display_request(
        name, node, "new evaluation", masked=ACTIVE_MASKED_VALUE.get()
    ) as request:
        if request is not None:
            request.kind = "call"
            request.evaluation_id = (
                ACTIVE_VERBOSE_CONTEXT.get().evaluation_id or allocate_verbose_id("E")
            )
            creation = next(
                (
                    child
                    for child in parent.children
                    if child is not request and child.name == name and child.kind == "binding"
                ),
                None,
            )
            if creation is not None:
                parent.children.remove(creation)
                request.children.extend(creation.children)
        yield request


def record_display_value(name: str, value: object, source: str, *, masked: bool = False) -> None:
    """Add local or mapping leaves only when Frame lookup has not supplied a child.

    :param name: Already-read name.
    :param value: Resolved value already supplied by the operation.
    :param source: Accurate argument, external or unknown provenance.
    :param masked: Sticky diagnostic redaction before representation.
    """
    parent = ACTIVE_DISPLAY_REQUEST.get()
    if (is_verbose_enabled() or ACTIVE_DISPLAY_CAPTURE.get() is not None) and parent is not None:
        previous = next((child for child in parent.children if child.name == name), None)
        if previous is not None and previous.kind != "value":
            return
        payload = render_display_value(value, masked=masked or parent.masked)
        label = f"{name}: {payload} ({source})"
        if previous is None:
            parent.children.append(DisplayRequest(name, label, source, kind="value"))
        else:
            previous.label = label


def finish_display_request(request: DisplayRequest) -> None:
    """Publish one completed root tree to its current display consumers.

    :param request: Root whose operation has already returned successfully.
    """
    if not is_verbose_enabled() and ACTIVE_DISPLAY_CAPTURE.get() is None:
        return
    tree = request.freeze()
    capture = ACTIVE_DISPLAY_CAPTURE.get()
    if capture is not None:
        capture.tree = tree
        capture.result = request.result if request.execution == "new evaluation" else None
    if request.execution != "new evaluation":
        return
    details = () if request.result is None else (("Result", request.result),)
    identity = "" if request.evaluation_id is None else f" (evaluation {request.evaluation_id})"
    target = ACTIVE_TARGET_EXPRESSION.get()
    if request.kind == "target" and target is not None:
        using = ACTIVE_USING_DIAGNOSTICS.get()
        span = target.span if using is None else using.span
        original = safe_repr(
            "\n".join(render_source_excerpt(span, underline=False)),
            renderer=str,
            masked=request.masked,
        )
        emit_verbose_record(
            "evaluate",
            f"Resolved using target: {request.result} "
            f"({render_definition_location(span)}){identity}",
            context_details=(("Input", original), ("Target", request.label)),
            tree=tree,
            evaluation_id=request.evaluation_id,
            show_tree=False,
        )
        return
    emit_verbose_record(
        "evaluate",
        f"Evaluation tree for {request.name}{identity}",
        details=details,
        tree=tree,
        evaluation_id=request.evaluation_id,
    )
