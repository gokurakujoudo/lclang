"""CLI override partitioning for loader and runtime Frame layers."""

from __future__ import annotations

from typing import cast

from lclang.ast import LclAstNode
from lclang.cli.models import CliParams
from lclang.cli.parser import lazy_override_expression
from lclang.diagnostics import internal_masked_scope
from lclang.errors import LclCliUsageError, LclSyntaxError
from lclang.lang import parse_expression
from lclang.runtime import Frame
from lclang.source import SourceOrigin, SourceSpan
from lclang.types import SourceName


def forced_override_expression(value: str, *, masked: bool = False) -> LclAstNode | None:
    """Strictly parse an exact marked RESULT override.

    :param value: Exact raw RESULT token.
    :param masked: Whether the diagnostic excerpt must be redacted.
    :returns: Parsed expression, or ``None`` when *value* is not marked.
    :raises LclCliUsageError: If an exact marker contains invalid LCL.
    """
    if not value.startswith("LCL[") or not value.endswith("]"):
        return None
    try:
        return parse_expression(
            value[4:-1],
            origin=SourceOrigin(SourceName("RESULT")),
        )
    except LclSyntaxError as error:
        span = cast(SourceSpan, error.span)
        start = 4 + span.start.offset
        end = max(start + 1, 4 + span.end.offset)
        if masked:
            excerpt = "RESULT=<masked>"
        else:
            token = f"RESULT={value}"
            underline = " " * (len("RESULT=") + start) + "^" * (end - start)
            excerpt = f"{token}\n{underline}"
        raise LclCliUsageError(f"forced RESULT parse failed: {error}\n{excerpt}") from error


def partition_overrides(
    params: CliParams,
) -> tuple[dict[str, LclAstNode], dict[str, object]]:
    """Split raw CLI overrides into lazy definitions and literal values.

    :param params: Parsed invocation parameters.
    :returns: Definition and literal dictionaries.
    """
    definitions: dict[str, LclAstNode] = {}
    values: dict[str, object] = {}
    for name, value in params.overrides.items():
        if isinstance(value, bool):
            values[name] = value
            continue
        masked = name in params.masked_names
        with internal_masked_scope(masked):
            expression = lazy_override_expression(value)
        if expression is None:
            values[name] = value
        else:
            definitions[name] = expression
    return definitions, values


def require_forced_result(
    params: CliParams,
    definitions: dict[str, LclAstNode],
    inherited: Frame,
) -> None:
    """Validate a marked RESULT that permissive parsing left literal.

    :param params: Parsed invocation parameters.
    :param definitions: Already parsed override definitions.
    :param inherited: Loaded Frame supplying sticky masking policy.
    :returns: ``None`` after accepting unwrapped or valid marked RESULT text.
    :raises LclCliUsageError: If an exact RESULT marker contains invalid LCL.
    """
    value = params.overrides.get("RESULT")
    if not isinstance(value, str) or "RESULT" in definitions:
        return
    masked = "RESULT" in params.masked_names or inherited.is_masked("RESULT")
    with internal_masked_scope(masked):
        forced_override_expression(value, masked=masked)
