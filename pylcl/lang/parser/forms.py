"""Parsing for function, raise, and assert complete-expression forms."""

from __future__ import annotations

from collections.abc import Callable

from pylcl.ast import LclAssert, LclAstNode, LclFunction, LclParameter, LclRaise
from pylcl.ast.forms import ParameterKind
from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind
from pylcl.lang.parser.stream import TokenStream
from pylcl.source import SourceSpan
from pylcl.types import VarName


class _FormParser:
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
        """Dispatch to the form parser selected by the current keyword.

        :returns: Function, raise, or assert AST node, or ``None`` when the
           current token is not a supported form keyword.

        .. note::
           Unrecognized lookahead is non-consuming so the enclosing parser can
           continue with another expression family.
        """
        kind = self.stream.current.kind
        if kind is TokenKind.KW_DEF:
            return self._function()
        if kind is TokenKind.KW_RAISE:
            return self._raise()
        if kind is TokenKind.KW_ASSERT:
            return self._assert()
        return None

    def _function(self) -> LclFunction:
        """Parse a function form with parameters and a complete body.

        :returns: Immutable function AST node with its complete source span.
        :raises LclSyntaxError: If parameter ordering, delimiters, or the
           function body syntax is invalid.

        .. note::
           Parameter defaults are parsed as nonconditional expressions, while
           the body uses the complete-expression callback.
        """
        opening = self.stream.advance()
        self.stream.expect(TokenKind.LPAREN, "function form requires parameter parentheses")
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
            parameter = self._parameter(
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
        self.stream.expect(TokenKind.COLON, "function form requires body colon")
        body = self.parse_complete()
        return LclFunction(
            tuple(parameters),
            body,
            span=_merge_span(opening.span, body.span),
        )

    def _parameter(
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
            span=_merge_span(start, end),
        )

    def _raise(self) -> LclRaise:
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
        return LclRaise(value, span=_merge_span(opening.span, closing.span))

    def _assert(self) -> LclAssert:
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
        return LclAssert(condition, message, span=_merge_span(opening.span, closing.span))


def parse_form(
    stream: TokenStream,
    parse_complete: Callable[[], LclAstNode],
    parse_nonconditional: Callable[[], LclAstNode],
) -> LclAstNode | None:
    """Parse a complete-expression form when one begins at lookahead.

    :param stream: Token stream positioned at a possible form keyword.
    :param parse_complete: Callback parsing function bodies and form values.
    :param parse_nonconditional: Callback parsing parameter defaults.
    :returns: Parsed form node, or ``None`` when lookahead is not a form keyword.
    :raises LclSyntaxError: If recognized form syntax or parameters are invalid.

    .. note::
       A ``None`` result never consumes a token.
    """
    return _FormParser(stream, parse_complete, parse_nonconditional).parse()


def _merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the boundary spans of one function-like form.

    :param first: Span at the opening keyword or marker.
    :param last: Span at the final consumed expression or delimiter.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The source origin is inherited from *first*, and all intervening form
       syntax is covered by the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
