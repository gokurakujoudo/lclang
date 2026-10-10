"""Task-local read journals frozen only when expression evaluation fails."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal, cast

from lclang.ast import LclAstNode
from lclang.diagnostics import ACTIVE_MASKED_VALUE
from lclang.error import LclEvaluationError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.language import Code as language_codes
from lclang.error.context import DiagnosticValue, EvaluationContextFrame
from lclang.lang.printer import to_source
from lclang.scopes import ScopedProxyValue
from lclang.source import SourceSpan
from lclang.utils.representation import safe_repr


@guard_constructor(LclValidationError, language_codes.NATIVE_131)
@dataclass(slots=True)
class EvaluationReadJournal:
    """Own transient read evidence for one active expression or function call.

    :param name: Actual definition or lexical owner label.
    :param node: Expression whose source is retained until the scope ends.
    :param kind: Unitless definition, function, or dynamic-target category.
    :param masked: Whether the expression owner is masked.
    :param reads: Last successful value at each first-ordered name occurrence.
    """

    name: str
    node: LclAstNode
    kind: Literal["definition", "function", "target"]
    masked: bool
    reads: dict[tuple[str, SourceSpan], tuple[object, bool]] = field(
        default_factory=dict[tuple[str, SourceSpan], tuple[object, bool]]
    )


# Task-local active scopes come from evaluator entry and lexical function calls.
# The unitless empty tuple denotes no evaluation. Each newly entered scope owns
# its read dictionary; inherited scopes remain read-only to nested owner tasks.
ACTIVE_EVALUATION_CONTEXT: ContextVar[tuple[EvaluationReadJournal, ...]] = ContextVar(
    "lclang_evaluation_context", default=()
)

# Unitless, task-local AST identity identifies the loader's generated target
# definition. None means ordinary evaluation, preserving same-name user bindings.
ACTIVE_TARGET_EXPRESSION: ContextVar[LclAstNode | None] = ContextVar(
    "lclang_target_expression", default=None
)


@contextmanager
def collect_evaluation_context(
    name: str, node: LclAstNode, *, kind: Literal["definition", "function", "target"] = "definition"
) -> Generator[None]:
    """Own one active read journal and restore the previous task-local path.

    :param name: Actual qualified definition or lexical owner name.
    :param node: Expression being evaluated within the scope.
    :param kind: Category used by the human diagnostic renderer.
    :returns: Context manager restoring the prior path on success, failure, or cancellation.
    """
    journal = EvaluationReadJournal(name, node, kind, ACTIVE_MASKED_VALUE.get())
    token = ACTIVE_EVALUATION_CONTEXT.set((*ACTIVE_EVALUATION_CONTEXT.get(), journal))
    try:
        yield
    finally:
        ACTIVE_EVALUATION_CONTEXT.reset(token)


@guard_failure(LclEvaluationError, language_codes.NATIVE_131)
def record_value_read(name: str, value: object, span: SourceSpan, *, masked: bool = False) -> None:
    """Record an already resolved value without invoking its representation.

    :param name: Actual runtime or lexical binding name.
    :param value: Successfully resolved value; proxies are omitted until leaf lookup.
    :param span: Source occurrence used for stable deduplication.
    :param masked: Exact-name mask selected by the supplying resolver.
    """
    context = ACTIVE_EVALUATION_CONTEXT.get()
    if not context or isinstance(value, ScopedProxyValue):
        return
    journal = context[-1]
    key = (name, span)
    previous = journal.reads.get(key)
    sticky_mask = masked or journal.masked or (previous is not None and previous[1])
    journal.reads[key] = (value, sticky_mask)


@guard_failure(LclEvaluationError, language_codes.NATIVE_131)
def capture_evaluation_context() -> tuple[EvaluationContextFrame, ...]:
    """Detach protected source and value snapshots for the active failure path.

    :returns: Immutable records retaining no Frame, resolver, AST, or host value.
    """
    records: list[EvaluationContextFrame] = []
    for journal in ACTIVE_EVALUATION_CONTEXT.get():
        used = tuple(
            DiagnosticValue(
                name, span, type(value).__name__, safe_repr(value, masked=masked), masked
            )
            for (name, span), (value, masked) in journal.reads.items()
        )
        expression = safe_repr(
            journal.node, renderer=render_ast_source, max_length=None, masked=journal.masked
        )
        records.append(
            EvaluationContextFrame(
                journal.name,
                journal.node.span,
                expression,
                used,
                journal.kind,
                journal.masked,
            )
        )
    return tuple(records)


@guard_failure(LclEvaluationError, language_codes.NATIVE_131)
def render_ast_source(value: object) -> str:
    """Render a journal's known semantic node through the canonical printer.

    :param value: Semantic AST supplied by the journal capture boundary.
    :returns: Canonical expression source, without any host-value evaluation.
    """
    return to_source(cast(LclAstNode, value))
