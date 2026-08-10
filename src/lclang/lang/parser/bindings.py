"""Shared validation for names introduced by LCL syntax."""

from lclang.errors import LclSyntaxError
from lclang.lang.lexer import Token


def validate_binding_name(token: Token) -> None:
    """Reject a reserved double-underscore binding token.

    :param token: Identifier token used at a binding site.
    :returns: ``None``.
    :raises LclSyntaxError: If its spelling begins with two underscores.

    .. note::
       Ordinary references, attributes, and call keywords are not binding sites.
    """
    if token.lexeme.startswith("__"):
        raise LclSyntaxError(
            "binding name cannot start with double underscore",
            span=token.span,
        )
