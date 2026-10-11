"""Readable expression parse records with protected canonical source.

Defines ``trace_parse_result``.
"""

from lclang.error.mask_scope import ACTIVE_MASKED_VALUE
from lclang.error.source_excerpt import render_source_location
from lclang.error.verbose_diagnostic import internal_verbose_enabled
from lclang.error.verbose_records import emit_verbose_record
from lclang.lang.ast import LclAstNode
from lclang.lang.engine.printer import to_source
from lclang.utils.value_representation import safe_repr


def trace_parse_result(text: str, node: LclAstNode) -> None:
    """Show original source once and adapted source only when it differs.

    :param text: Original expression text already supplied to parsing.
    :param node: Successfully parsed or adapted AST.
    """
    if not internal_verbose_enabled():
        return
    masked = ACTIVE_MASKED_VALUE.get()
    original = safe_repr(text.strip(), renderer=str, masked=masked)
    canonical = safe_repr(node, renderer=lambda value: to_source(node), masked=masked)
    details = [("Source", render_source_location(node.span)), ("Expression", original)]
    if original.strip() != canonical:
        details.append(("Parsed expression", canonical))
    emit_verbose_record(
        "parse", f"Parsed an expression as {type(node).__name__}", details=tuple(details)
    )
