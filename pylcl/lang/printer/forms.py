"""Canonical rendering for function, error, and control forms."""

from __future__ import annotations

from pylcl.ast import (
    LclAssert,
    LclAstNode,
    LclExceptHandler,
    LclFunction,
    LclParameter,
    LclRaise,
    LclTry,
    LclWith,
    LclWithItem,
    ParameterKind,
)
from pylcl.lang.printer._types import Render, RenderResult

FORM_PRECEDENCE = 5


def render_form(node: LclAstNode, render: Render) -> RenderResult | None:
    """Render a function, error, or control expression form.

    :param node: Candidate AST node.
    :param render: Recursive dispatcher for nested expressions.
    :returns: Canonical source and precedence, or ``None`` for another family.

    .. note::
       Form bodies use the lowest parent precedence to retain full expressions.
    """
    if isinstance(node, LclFunction):
        parameters = ", ".join(_parameter(value, render) for value in node.parameters)
        return f"def ({parameters}): {render(node.body, 0)}", FORM_PRECEDENCE
    if isinstance(node, LclRaise):
        return f"raise({render(node.value, 0)})", FORM_PRECEDENCE
    if isinstance(node, LclAssert):
        message = "" if node.message is None else f", {render(node.message, 0)}"
        return f"assert({render(node.condition, 0)}{message})", FORM_PRECEDENCE
    if isinstance(node, LclTry):
        return _try(node, render), FORM_PRECEDENCE
    if isinstance(node, LclWith):
        items = ", ".join(_with_item(value, render) for value in node.items)
        return f"with {items}: {render(node.body, 0)}", FORM_PRECEDENCE
    return None


def _parameter(node: LclParameter, render: Render) -> str:
    """Render one function parameter and its optional default.

    :param node: Parameter node to render.
    :param render: Recursive dispatcher for the default expression.
    :returns: Canonical parameter source text.

    .. note::
       Variadic parameter kinds receive their ``*`` or ``**`` marker while
       positional and keyword-only parameters remain unmarked.
    """
    prefix = {
        ParameterKind.POSITIONAL: "",
        ParameterKind.KEYWORD_ONLY: "",
        ParameterKind.VAR_POSITIONAL: "*",
        ParameterKind.VAR_KEYWORD: "**",
    }[node.kind]
    default = "" if node.default is None else f"={render(node.default, 0)}"
    return f"{prefix}{node.name}{default}"


def _try(node: LclTry, render: Render) -> str:
    """Render a try expression with handlers and optional finalization.

    :param node: Try-form node to render.
    :param render: Recursive dispatcher for bodies and handler expressions.
    :returns: Canonical try-form source text.

    .. note::
       Handlers remain in their AST order, followed by the optional ``finally``
       body.
    """
    text = f"try: {render(node.body, 0)}"
    text += "".join(_handler(handler, render) for handler in node.handlers)
    if node.finally_body is not None:
        text += f" finally: {render(node.finally_body, 0)}"
    return text


def _handler(node: LclExceptHandler, render: Render) -> str:
    """Render one exception handler and its recovery body.

    :param node: Exception-handler node to render.
    :param render: Recursive dispatcher for the exception matcher and body.
    :returns: Canonical exception-handler source text.

    .. note::
       A missing matcher renders a catch-all handler, and a binding name is
       emitted only when the handler supplies one.
    """
    matcher = ""
    if node.exception is not None:
        matcher = f" {render(node.exception, 0)}"
        if node.name is not None:
            matcher += f" as {node.name}"
    return f" except{matcher}: {render(node.body, 0)}"


def _with_item(node: LclWithItem, render: Render) -> str:
    """Render one context-manager item and its optional target.

    :param node: Context-manager item node to render.
    :param render: Recursive dispatcher for the context expression.
    :returns: Canonical with-item source text.
    """
    target = "" if node.target is None else f" as {node.target}"
    return f"{render(node.context, 0)}{target}"
