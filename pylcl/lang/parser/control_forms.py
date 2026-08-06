"""Parsing for try and with complete-expression control forms."""

from __future__ import annotations

from collections.abc import Callable

from pylcl.ast import LclAstNode, LclExceptHandler, LclTry, LclWith, LclWithItem
from pylcl.errors import LclSyntaxError
from pylcl.lang.lexer import TokenKind
from pylcl.lang.parser.stream import TokenStream
from pylcl.source import SourceSpan
from pylcl.types import VarName


class _ControlFormParser:
    """Parse try and with forms from a shared token stream.

    .. note::
       The parser keeps the supplied callbacks so nested bodies use the same
       precedence-aware parser as the surrounding expression.
    """

    def __init__(
        self,
        stream: TokenStream,
        parse_complete: Callable[[], LclAstNode],
        parse_nonconditional: Callable[[], LclAstNode],
    ) -> None:
        """Bind the stream and nested-expression parsing callbacks.

        :param stream: Token stream positioned at a possible control keyword.
        :param parse_complete: Callback parsing complete body expressions.
        :param parse_nonconditional: Callback parsing matcher and context
           expressions without a trailing conditional.
        :returns: ``None``.

        .. note::
           Collaborators are retained by reference for the lifetime of this
           short-lived parser helper.
        """
        self.stream = stream
        self.parse_complete = parse_complete
        self.parse_nonconditional = parse_nonconditional

    def parse(self) -> LclAstNode | None:
        """Dispatch to the control-form parser selected by lookahead.

        :returns: Parsed try or with node, or ``None`` when the current token
           is not a control-form keyword.

        .. note::
           Unrecognized lookahead is non-consuming, allowing the enclosing
           Pratt parser to try another expression family.
        """
        if self.stream.current.kind is TokenKind.KW_TRY:
            return self._try()
        if self.stream.current.kind is TokenKind.KW_WITH:
            return self._with()
        return None

    def _try(self) -> LclTry:
        """Parse a try body, its handlers, and an optional finally body.

        :returns: Complete :class:`~pylcl.ast.LclTry` node with source span.
        :raises LclSyntaxError: If handler ordering or required try syntax is
           invalid.

        .. note::
           A bare ``except`` is permitted only as the final handler, and a try
           form must contain at least one handler or a finally body.
        """
        opening = self.stream.advance()
        self.stream.expect(TokenKind.COLON, "try form requires body colon")
        body = self.parse_complete()
        handlers: list[LclExceptHandler] = []
        bare_seen = False
        while (marker := self.stream.match(TokenKind.KW_EXCEPT)) is not None:
            if bare_seen:
                raise LclSyntaxError("bare except handler must be last", span=marker.span)
            exception = None
            name = None
            if self.stream.current.kind is not TokenKind.COLON:
                exception = self.parse_nonconditional()
                if self.stream.match(TokenKind.KW_AS) is not None:
                    name_token = self.stream.expect(
                        TokenKind.IDENTIFIER,
                        "except as requires a target name",
                    )
                    name = VarName(name_token.lexeme)
            else:
                bare_seen = True
            self.stream.expect(TokenKind.COLON, "except handler requires body colon")
            handler_body = self.parse_complete()
            handlers.append(
                LclExceptHandler(
                    exception,
                    name,
                    handler_body,
                    span=_merge_span(marker.span, handler_body.span),
                )
            )
        finally_body = None
        if self.stream.match(TokenKind.KW_FINALLY) is not None:
            self.stream.expect(TokenKind.COLON, "finally requires body colon")
            finally_body = self.parse_complete()
        if not handlers and finally_body is None:
            raise LclSyntaxError("try form requires except or finally", span=body.span)
        final = finally_body or handlers[-1].body
        return LclTry(
            body,
            tuple(handlers),
            finally_body,
            span=_merge_span(opening.span, final.span),
        )

    def _with(self) -> LclWith:
        """Parse comma-separated context items followed by a body.

        :returns: Complete :class:`~pylcl.ast.LclWith` node with source span.
        :raises LclSyntaxError: If a context item, optional target, or body
           delimiter is malformed.

        .. note::
           Each optional ``as`` target is stored with its context expression,
           preserving item order for later evaluation and cleanup.
        """
        opening = self.stream.advance()
        items: list[LclWithItem] = []
        while True:
            context = self.parse_nonconditional()
            target = None
            end = context.span
            if self.stream.match(TokenKind.KW_AS) is not None:
                target_token = self.stream.expect(
                    TokenKind.IDENTIFIER,
                    "with as requires a target name",
                )
                target = VarName(target_token.lexeme)
                end = target_token.span
            items.append(
                LclWithItem(
                    context,
                    target,
                    span=_merge_span(context.span, end),
                )
            )
            if self.stream.match(TokenKind.COMMA) is None:
                break
        self.stream.expect(TokenKind.COLON, "with form requires body colon")
        body = self.parse_complete()
        return LclWith(tuple(items), body, span=_merge_span(opening.span, body.span))


def parse_control_form(
    stream: TokenStream,
    parse_complete: Callable[[], LclAstNode],
    parse_nonconditional: Callable[[], LclAstNode],
) -> LclAstNode | None:
    """Parse a try or with form when one begins at lookahead.

    :param stream: Token stream positioned at a possible control keyword.
    :param parse_complete: Callback parsing bodies and handler expressions.
    :param parse_nonconditional: Callback parsing matchers and context items.
    :returns: Parsed control node, or ``None`` without consuming other syntax.
    :raises LclSyntaxError: If recognized control syntax or ordering is invalid.

    .. note::
       Handler and item order is retained exactly as written.
    """
    return _ControlFormParser(
        stream,
        parse_complete,
        parse_nonconditional,
    ).parse()


def _merge_span(first: SourceSpan, last: SourceSpan) -> SourceSpan:
    """Join the boundary spans of one control-form node.

    :param first: Span at the beginning of the construct.
    :param last: Span at its final consumed expression or token.
    :returns: Half-open span from *first* start through *last* end.

    .. note::
       The source origin is inherited from *first*, and intervening syntax is
       covered by the resulting range.
    """
    return SourceSpan(first.origin, first.start, last.end)
