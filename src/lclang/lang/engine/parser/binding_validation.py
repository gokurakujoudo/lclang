"""Shared validation for names introduced by LCL syntax.

Defines ``validate_binding_name``.
"""

from lclang.error import LanguageErrorCode, LclSyntaxError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_failure
from lclang.lang.engine.lexer import Token


@guard_failure(LclValidationError, LanguageErrorCode.E23_BINDING_VALIDATION_NATIVE_FAILURE)
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
            code=LanguageErrorCode.E23_BINDING_NAME_CANNOT_START_WITH_DOUBLE_UNDERSCORE,
        )
