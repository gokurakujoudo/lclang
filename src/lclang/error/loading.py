"""Copy loading context while retaining codes, native causes, and source ranges."""

from lclang.error.base import LclError
from lclang.error.codes.configuration import Code as configuration_codes
from lclang.error.context import ConfigLoadFrame
from lclang.error.families import LclConfigError
from lclang.error.wrapping import wrap_failure
from lclang.source import SourceSpan


def derive_loading_error(error: Exception, frame: ConfigLoadFrame) -> LclError:
    """Attach a caller-specific loading placement to a detached structured failure.

    :param error: Existing LCL failure or native failure at the loading boundary.
    :param frame: Root or source-introduction placement for this caller.
    :returns: LCL diagnostic preserving its code, original cause, traceback, and source range.
    :raises LclValidationError: If frame is not a ConfigLoadFrame.
    """
    failure = wrap_failure(error, LclConfigError, configuration_codes.LOADING_FAILURE)
    if not isinstance(error, LclError):
        span = error.__dict__.get("source_span")
        if isinstance(span, SourceSpan):
            failure.span = span
    return failure.derive_config_context(frame)
