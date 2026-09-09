"""Parsing for function, raise, and assert complete-expression forms."""

from __future__ import annotations

from collections.abc import Callable

from lclang.ast import LclAssert, LclAstNode, LclFunction, LclParameter, LclRaise
from lclang.ast.forms import ParameterKind
from lclang.errors import LclSyntaxError
from lclang.lang.lexer import TokenKind
from lclang.lang.parser.bindings import validate_binding_name
from lclang.lang.parser.stream import TokenStream
from lclang.source import merge_source_spans
from lclang.types import VarName


class InternalFormParser:
    """Parse function, raise, and assert forms from a shared token stream.

    .. note::
       Nested-expression callbacks are retained so form bodies and defaults
       use the surrounding parser's precedence and version rules.
    """

    def __init__(
        self,
        stream: TokenStream,
        parse_complete: Callable[[], LclAstNode],
        parse_nonconditional: Callable[[], LclAstNode],
    ) -> None:
        """Bind the stream and callbacks used by form parsing.

        :param stream: Token stream positioned at a possible form keyword.
        :param parse_complete: Callback parsing complete form bodies and
           values.
        :param parse_nonconditional: Callback parsing parameter defaults.
        :returns: ``None``.

        .. note::
           The callbacks are retained by reference only for this parser
           helper's lifetime.
        """
        self.stream = stream
        self.parse_complete = parse_complete
        self.parse_nonconditional = parse_nonconditional

    def parse(self) -> LclAstNode | None:
        """Dispatch to the form parser selected by current lookahead.

        :returns: Function, raise, or assert AST node, or ``None`` when
           lookahead does not begin a supported form.
        .. note::
           Unrecognized lookahead is non-consuming so the enclosing parser can
           continue with another expression family.
        """
        kind = self.stream.current.kind
        if kind is TokenKind.IDENTIFIER and self.stream.peek(1).kind is TokenKind.ARROW:
            return self.internal_bare_function()
        if kind is TokenKind.LPAREN and self.internal_parenthesized_function_ahead():
            return self.internal_function()
        if kind is TokenKind.KW_RAISE:
            return self.internal_raise()
        if kind is TokenKind.KW_ASSERT:
            return self.internal_assert()
        return None

    def internal_parenthesized_function_ahead(self) -> bool:
        """Return whether the matching parenthesis is followed by an arrow.

        :returns: ``True`` for a parenthesized function signature.

        .. note::
           Balanced lookahead is non-consuming, so ordinary grouped and tuple
           expressions remain available to the atom parser.
        """
        depth = 0
        offset = 0
        while True:
            kind = self.stream.peek(offset).kind
            if kind is TokenKind.EOF:
                return False
            if kind is TokenKind.LPAREN:
                depth += 1
            elif kind is TokenKind.RPAREN:
                depth -= 1
                if depth == 0:
                    return self.stream.peek(offset + 1).kind is TokenKind.ARROW
            offset += 1

    def internal_bare_function(self) -> LclFunction:
        """Parse the shorthand form for one required positional parameter.

        :returns: Immutable single-parameter function AST node.
        :raises LclSyntaxError: If the binding is reserved or the body is
           missing or malformed.

        .. note::
           The shorthand creates the same parameter value as ``(name) ->``;
           source style is intentionally absent from the semantic AST.
        """
        name_token = self.stream.advance()
        validate_binding_name(name_token)
        self.stream.expect(TokenKind.ARROW, "function form requires arrow")
        body = self.parse_complete()
        parameter = LclParameter(
            VarName(name_token.lexeme),
            ParameterKind.POSITIONAL,
            span=name_token.span,
        )
        return LclFunction(
            (parameter,),
            body,
            span=merge_source_spans(name_token.span, body.span),
        )

    def internal_function(self) -> LclFunction:
        """Parse a function form with parameters and a complete body.

        :returns: Immutable function AST node with its complete source span.
        :raises LclSyntaxError: If parameter ordering, delimiters, or the
           function body syntax is invalid.

        .. note::
           Parameter defaults are parsed as nonconditional expressions, while
           the body uses the complete-expression callback.
        """
        opening = self.stream.advance()
        parameters: list[LclParameter] = []
        names: set[str] = set()
        keyword_only = False
        seen_default = False
        seen_var_keyword = False
        while self.stream.current.kind is not TokenKind.RPAREN:
            if seen_var_keyword:
                raise LclSyntaxError(
                    "parameter follows variadic keyword",
                    span=self.stream.current.span,
                )
            parameter = self.internal_parameter(
                keyword_only=keyword_only,
                seen_default=seen_default,
                names=names,
            )
            parameters.append(parameter)
            keyword_only |= parameter.kind is ParameterKind.VAR_POSITIONAL
            seen_var_keyword |= parameter.kind is ParameterKind.VAR_KEYWORD
            if parameter.kind is ParameterKind.POSITIONAL and parameter.default is not None:
                seen_default = True
            if self.stream.match(TokenKind.COMMA) is None:
                break
            if self.stream.peek().kind is TokenKind.RPAREN:
                break
        self.stream.expect(TokenKind.RPAREN, "expected closing parameter parenthesis")
        self.stream.expect(TokenKind.ARROW, "function form requires arrow")
        body = self.parse_complete()
        return LclFunction(
            tuple(parameters),
            body,
            span=merge_source_spans(opening.span, body.span),
        )

    def internal_parameter(
        self,
        *,
        keyword_only: bool,
        seen_default: bool,
        names: set[str],
    ) -> LclParameter:
        """Parse one positional, keyword-only, or variadic parameter.

        :param keyword_only: Whether preceding ``*`` made this parameter
           keyword-only.
        :param seen_default: Whether a positional default was already parsed.
        :param names: Mutable set of parameter names already declared.
        :returns: Immutable parameter AST node.
        :raises LclSyntaxError: If the name, default, or parameter ordering is
           invalid.

        .. note::
           The supplied name set is updated in place so duplicate names are
           rejected across the complete function signature.
        """
        marker = self.stream.match(TokenKind.DOUBLE_STAR)
        kind = ParameterKind.VAR_KEYWORD if marker is not None else None
        if kind is None:
            marker = self.stream.match(TokenKind.STAR)
            if marker is not None:
                kind = ParameterKind.VAR_POSITIONAL
        name_token = self.stream.expect(TokenKind.IDENTIFIER, "expected parameter name")
        validate_binding_name(name_token)
        if name_token.lexeme in names:
            raise LclSyntaxError("duplicate function parameter", span=name_token.span)
        names.add(name_token.lexeme)
        if kind is None:
            kind = ParameterKind.KEYWORD_ONLY if keyword_only else ParameterKind.POSITIONAL
        default = None
        if self.stream.match(TokenKind.EQUAL) is not None:
            if kind in {ParameterKind.VAR_POSITIONAL, ParameterKind.VAR_KEYWORD}:
                raise LclSyntaxError(
                    "variadic parameter cannot have a default",
                    span=name_token.span,
                )
            default = self.parse_nonconditional()
        elif kind is ParameterKind.POSITIONAL and seen_default:
            raise LclSyntaxError("required parameter follows default", span=name_token.span)
        end = name_token.span if default is None else default.span
        start = name_token.span if marker is None else marker.span
        return LclParameter(
            VarName(name_token.lexeme),
            kind,
            default,
            span=merge_source_spans(start, end),
        )

    def internal_raise(self) -> LclRaise:
        """Parse a parenthesized raise form.

        :returns: Immutable raise AST node with a complete source span.

        .. note::
           The raised value is parsed as a complete expression, preserving
           nested control and conditional forms inside the parentheses.
        """
        opening = self.stream.advance()
        self.stream.expect(TokenKind.LPAREN, "raise form requires opening parenthesis")
        value = self.parse_complete()
        closing = self.stream.expect(TokenKind.RPAREN, "raise form requires closing parenthesis")
        return LclRaise(value, span=merge_source_spans(opening.span, closing.span))

    def internal_assert(self) -> LclAssert:
        """Parse an assertion with an optional message expression.

        :returns: Immutable assert AST node with a complete source span.

        .. note::
           The optional message is recognized only after a comma and is parsed
           with the same complete-expression callback as the condition.
        """
        opening = self.stream.advance()
        self.stream.expect(TokenKind.LPAREN, "assert form requires opening parenthesis")
        condition = self.parse_complete()
        message = None
        if self.stream.match(TokenKind.COMMA) is not None:
            message = self.parse_complete()
        closing = self.stream.expect(TokenKind.RPAREN, "assert form requires closing parenthesis")
        return LclAssert(condition, message, span=merge_source_spans(opening.span, closing.span))


def parse_form(
    stream: TokenStream,
    parse_complete: Callable[[], LclAstNode],
    parse_nonconditional: Callable[[], LclAstNode],
) -> LclAstNode | None:
    """Parse a complete-expression form when one begins at lookahead.

    :param stream: Token stream positioned at a possible complete form.
    :param parse_complete: Callback parsing function bodies and form values.
    :param parse_nonconditional: Callback parsing parameter defaults.
    :returns: Parsed form node, or ``None`` when lookahead is not a form.
    :raises LclSyntaxError: If recognized form syntax or parameters are invalid.

    .. note::
       A ``None`` result never consumes a token.
    """
    return InternalFormParser(stream, parse_complete, parse_nonconditional).parse()
