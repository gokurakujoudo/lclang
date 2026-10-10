"""Copy loading context while retaining codes, native causes, and source ranges.

Defines ``derive_loading_error``.
"""

from lclang.common.source_location import SourceSpan
from lclang.error.codes.e3_configuration_error_code import ConfigurationErrorCode
from lclang.error.diagnostic_records import ConfigLoadFrame
from lclang.error.exception_base import LclError
from lclang.error.exception_family import LclConfigError
from lclang.error.native_wrap import wrap_failure


def derive_loading_error(error: Exception, frame: ConfigLoadFrame) -> LclError:
    """Attach a caller-specific loading placement to a detached structured failure.

    :param error: Existing LCL failure or native failure at the loading boundary.
    :param frame: Root or source-introduction placement for this caller.
    :returns: LCL diagnostic preserving its code, original cause, traceback, and source range.
    :raises LclValidationError: If frame is not a ConfigLoadFrame.
    """
    failure = wrap_failure(error, LclConfigError, ConfigurationErrorCode.E23_LOADING_FAILURE)
    if not isinstance(error, LclError):
        span = error.__dict__.get("source_span")
        if isinstance(span, SourceSpan):
            failure.span = span
    return failure.derive_config_context(frame)
