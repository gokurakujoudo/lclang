"""Hygienic qualification of independently expanded configuration subtrees.

Defines ``qualify_import``, ``qualify_expression``, ``qualify_value``.
"""

from dataclasses import fields, replace
from typing import cast

from lclang.common.identifiers import VarName
from lclang.common.source_location import SourceSpan
from lclang.config.config_document import ConfigDefinition
from lclang.error import ConfigurationErrorCode, LclConfigError
from lclang.error.operation_guard import guard_failure
from lclang.lang.ast import LclAstNode, LclName
from lclang.lang.runtime.dependency.ast_dependency_analysis import analyze_dependencies


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def qualify_import(
    definitions: list[ConfigDefinition], namespace_names: set[str], alias: str
) -> tuple[list[ConfigDefinition], set[str]]:
    """Prefix an independently validated subtree and its local free references.

    :param definitions: Chronological definitions belonging to this occurrence.
    :param namespace_names: Explicit namespaces inside the subtree.
    :param alias: Validated destination qualified namespace.
    :returns: Qualified occurrences and explicit namespace reservations.
    """
    roots = {str(item.name).split(".", 1)[0] for item in definitions}
    roots.update(name.split(".", 1)[0] for name in namespace_names)
    output: list[ConfigDefinition] = []
    for definition in definitions:
        free = {
            (str(reference.name), reference.span)
            for reference in analyze_dependencies(definition.expression)
            if str(reference.name).split(".", 1)[0] in roots
        }
        output.append(
            replace(
                definition,
                name=VarName(f"{alias}.{definition.name}"),
                expression=qualify_expression(definition.expression, free, alias),
            )
        )
    return output, {alias, *(f"{alias}.{name}" for name in namespace_names)}


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def qualify_expression(
    node: LclAstNode, free: set[tuple[str, SourceSpan]], alias: str
) -> LclAstNode:
    """Rewrite selected free name nodes without capturing lexical bindings.

    :param node: Semantic AST retaining its physical source spans.
    :param free: Scope-aware free occurrences belonging to local defined roots.
    :param alias: Destination namespace prefix.
    :returns: Immutable equivalent AST using flat qualified name references.
    """
    if isinstance(node, LclName) and (str(node.identifier), node.span) in free:
        return replace(node, identifier=VarName(f"{alias}.{node.identifier}"))
    changes: dict[str, object] = {}
    for field in fields(node):
        original = getattr(node, field.name)
        transformed = qualify_value(original, free, alias)
        if transformed is not original:
            changes[field.name] = transformed
    return node if not changes else replace(node, **changes)  # type: ignore[arg-type]


@guard_failure(LclConfigError, ConfigurationErrorCode.E11_CONFIG_PARSING_NATIVE_FAILURE)
def qualify_value(value: object, free: set[tuple[str, SourceSpan]], alias: str) -> object:
    """Transform AST-valued fields and immutable child tuples.

    :param value: Frozen AST field or scalar metadata.
    :param free: Selected free-name occurrences.
    :param alias: Namespace prefix applied to selected occurrences.
    :returns: Original value or transformed semantic structure.
    """
    if isinstance(value, LclAstNode):
        return qualify_expression(value, free, alias)
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        transformed = tuple(qualify_value(item, free, alias) for item in items)
        return (
            items if all(a is b for a, b in zip(items, transformed, strict=True)) else transformed
        )
    return value
