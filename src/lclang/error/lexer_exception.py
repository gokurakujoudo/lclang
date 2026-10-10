"""Source-boundary exceptions used by LCL literal scanners.

Defines ``EscapeDecodeError``, ``InternalLiteralScanError``, ``FStringScanError``.
"""

from lclang.error.codes.e1_language_error_code import LanguageErrorCode
from lclang.error.exception_base import LclValidationError
from lclang.error.exception_family import LclSyntaxError
from lclang.error.operation_guard import guard_constructor


@guard_constructor(LclValidationError, LanguageErrorCode.E13_ESCAPE_DECODING_NATIVE_FAILURE)
class EscapeDecodeError(LclSyntaxError):
    """Report invalid literal content at a content-relative boundary.

    .. note::
       The lexer translates the relative boundary into an absolute source span.
    """

    def __init__(self, message: str, end: int, *, code: str | None = None) -> None:
        """Store a stable message and exclusive error boundary.

        :param message: Human-readable description of the invalid content.
        :param code: Classified cause from the detecting scanner.
        :param end: Content-relative exclusive offset for the diagnostic.
        :returns: ``None``.

        .. note::
           The offset is relative to the literal content rather than the
           complete source document.
        """
        super().__init__(message, code=code)
        self.message = message
        self.end = end


@guard_constructor(LclValidationError, LanguageErrorCode.E12_LITERAL_SCANNING_NATIVE_FAILURE)
class InternalLiteralScanError(LclSyntaxError):
    """Carry a literal error message and content-relative boundary.

    .. note::
       The public scanner adds the final source-aware diagnostic.
    """

    def __init__(self, message: str, end: int, *, code: str | None = None) -> None:
        """Store the malformed-literal details for the caller.

        :param message: Human-readable description of the malformed literal.
        :param code: Classified cause from the detecting scanner.
        :param end: Absolute exclusive source offset for the error.
        :returns: ``None``.

        .. note::
           The offset is already adjusted for escape-decoder failures.
        """
        super().__init__(message, code=code)
        self.message = message
        self.end = end


@guard_constructor(LclValidationError, LanguageErrorCode.E14_FSTRING_SCANNING_NATIVE_FAILURE)
class FStringScanError(LclSyntaxError):
    """Report invalid interpolation at an absolute source boundary.

    .. note::
       The outer scanner converts this internal boundary into ``LclSyntaxError``.
    """

    def __init__(self, message: str, end: int, *, code: str | None = None) -> None:
        """Store a stable message and exclusive error boundary.

        :param message: Human-readable description of the malformed f-string.
        :param code: Classified cause from the detecting scanner.
        :param end: Absolute exclusive source offset for the diagnostic.
        :returns: ``None``.

        .. note::
           The outer lexer translates this boundary into the final source
           span reported to callers.
        """
        super().__init__(message, code=code)
        self.message = message
        self.end = end
