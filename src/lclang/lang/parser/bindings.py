"""Shared validation for names introduced by LCL syntax."""

from lclang.error import LclSyntaxError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.language import Code as language_codes
from lclang.lang.lexer import Token


@guard_failure(LclValidationError, language_codes.NATIVE_123)
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
            code=language_codes.E23_BINDING_NAME_CANNOT_START_WITH_DOUBLE_UNDERSCORE,
        )
