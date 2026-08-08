"""Configuration-aware expression token adaptation and parsing."""

from dataclasses import fields, replace
from pathlib import Path

from pylcl.ast import LclAstNode, LclConstant, LclName
from pylcl.config.errors import LclConfigSyntaxError
from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import Token, TokenKind, scan_tokens
from pylcl.lang.parser.pratt import parse_tokens
from pylcl.source import SourceOrigin, SourcePosition


def parse_config_expression(
    text: str,
    *,
    origin: SourceOrigin,
    start: SourcePosition,
) -> LclAstNode:
    """Parse an expression with eager file-magic substitution.

    :param text: Position-preserving expression text.
    :param origin: Physical or synthetic source origin.
    :param start: Position of the expression text's first character.
    :returns: Immutable semantic AST containing no file-magic references.
    :raises LclConfigSyntaxError: If syntax is invalid or magic lacks a path.

    .. note::
       Token replacement preserves each magic identifier's original span.
    """
    try:
        tokens = scan_tokens(text, origin=origin, start=start)
        adapted = adapt_magic_tokens(tokens, origin.path)
        parsed = parse_tokens(adapted)
        return replace_magic_nodes(parsed, origin.path)
    except LclConfigSyntaxError:
        raise
    except LclSyntaxError as error:
        raise LclConfigSyntaxError(
            error.message,
            span=error.span,
        ) from error


def adapt_magic_tokens(tokens: list[Token], path: Path | None) -> list[Token]:
    """Replace standalone file-magic identifiers with string tokens.

    :param tokens: Source-aware expression tokens.
    :param path: Canonical physical source path, when available.
    :returns: Fresh token list with eager magic constants.
    :raises LclConfigSyntaxError: If magic occurs for a pathless source.

    .. note::
       String and comment contents are already literal tokens and remain unchanged.
    """
    values = None if path is None else {
        "__file__": str(path),
        "__dir__": str(path.parent),
    }
    output: list[Token] = []
    for token in tokens:
        if token.kind is TokenKind.IDENTIFIER and token.lexeme in {"__file__", "__dir__"}:
            if values is None:
                raise LclConfigSyntaxError(
                    "file magic requires a physical source path",
                    span=token.span,
                )
            output.append(Token(TokenKind.STRING, token.lexeme, token.span, values[token.lexeme]))
        else:
            output.append(token)
    return output


def replace_magic_nodes(node: LclAstNode, path: Path | None) -> LclAstNode:
    """Replace magic references nested inside semantic f-string fields.

    :param node: Parsed immutable AST node.
    :param path: Canonical physical source path, when available.
    :returns: Equivalent AST with every remaining magic reference constantized.
    :raises LclConfigSyntaxError: If pathless source contains nested magic.

    .. note::
       The generic frozen-dataclass traversal also covers future AST families.
    """
    if isinstance(node, LclName) and str(node.identifier) in {"__file__", "__dir__"}:
        if path is None:
            raise LclConfigSyntaxError(
                "file magic requires a physical source path",
                span=node.span,
            )
        value = str(path) if str(node.identifier) == "__file__" else str(path.parent)
        return LclConstant(value, span=node.span)
    changes: dict[str, object] = {}
    for item in fields(node):
        if item.name == "span":
            continue
        original = getattr(node, item.name)
        transformed = replace_magic_value(original, path)
        if transformed is not original:
            changes[item.name] = transformed
    return node if not changes else replace(node, **changes)  # type: ignore[arg-type]


def replace_magic_value(value: object, path: Path | None) -> object:
    """Transform an AST-valued field or immutable child tuple.

    :param value: Candidate dataclass field value.
    :param path: Canonical physical source path, when available.
    :returns: Original scalar or transformed immutable AST structure.

    .. note::
       Binding metadata is scalar and remains untouched.
    """
    if isinstance(value, LclAstNode):
        return replace_magic_nodes(value, path)
    if isinstance(value, tuple):
        transformed = tuple(replace_magic_value(item, path) for item in value)
        unchanged = all(
            left is right
            for left, right in zip(value, transformed, strict=True)
        )
        return value if unchanged else transformed
    return value
