"""Contextual qualification of attribute-chain dependencies.

Defines ``qualify_dependency_references``, ``attribute_path``.
"""

from __future__ import annotations

from collections.abc import Collection

from lclang.common.identifiers import VarName
from lclang.common.source_location import SourceSpan
from lclang.error import LclEvaluationError, RuntimeErrorCode
from lclang.error.operation_guard import guard_failure
from lclang.lang.ast import LclAstNode, LclAttribute, LclName, LclSafeAttribute
from lclang.lang.runtime.dependency.dependency_types import DependencyReference


@guard_failure(LclEvaluationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
def qualify_dependency_references(
    node: LclAstNode,
    references: tuple[DependencyReference, ...],
    scoped_names: Collection[str],
) -> tuple[DependencyReference, ...]:
    """Replace scoped roots with their longest attribute paths.

    :param node: Complete expression syntax.
    :param references: Scope-aware free-name references.
    :param scoped_names: Known real or placeholder scoped bindings.
    :returns: References retaining kinds with qualified names and spans.
    """
    roots = {name.split(".", 1)[0] for name in scoped_names if "." in name}
    replacements: dict[SourceSpan, tuple[str, SourceSpan]] = {}
    for item in node.walk():
        selected = attribute_path(item)
        if selected is None:
            continue
        root, parts = selected
        if str(root.identifier) not in roots:
            continue
        current = replacements.get(root.span)
        if current is None or len(parts) > current[0].count(".") + 1:
            replacements[root.span] = (".".join(parts), item.span)
    return tuple(
        (
            DependencyReference(
                VarName(replacements[reference.span][0]),
                reference.kind,
                replacements[reference.span][1],
            )
            if reference.span in replacements
            else reference
        )
        for reference in references
    )


@guard_failure(LclEvaluationError, RuntimeErrorCode.E41_DEPENDENCY_TRACE_NATIVE_FAILURE)
def attribute_path(node: LclAstNode) -> tuple[LclName, tuple[str, ...]] | None:
    """Return one pure name-rooted attribute path.

    :param node: Candidate primary node.
    :returns: Root name and complete segments, or ``None``.
    """
    parts: list[str] = []
    current = node
    while isinstance(current, (LclAttribute, LclSafeAttribute)):
        parts.append(str(current.name))
        current = current.value
    if not isinstance(current, LclName) or not parts:
        return None
    return current, (str(current.identifier), *reversed(parts))
