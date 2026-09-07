"""Safe single-line representations independent of runtime presentation state."""

from collections.abc import Callable

from lclang.masking import MASKED_VALUE

# Unitless names identify this module's public downstream interface; helper constants stay local.
__all__ = ["safe_repr"]

# Character budget from existing verbose diagnostics; 200 keeps ordinary values readable
# without flooding logs. The unitless marker explicitly identifies omitted content.
DEFAULT_REPR_LENGTH = 200
TRUNCATION_MARKER = "...<truncated>"


def safe_repr(
    value: object,
    *,
    max_length: int | None = DEFAULT_REPR_LENGTH,
    renderer: Callable[[object], str] | None = None,
    masked: bool = False,
) -> str:
    """Render a protected, single-line value within an optional character budget.

    :param value: Value passed to repr or the selected renderer.
    :param max_length: Nonnegative total character limit, or None for no truncation.
       Zero produces empty unmasked output. Short limits retain a marker prefix.
    :param renderer: Optional canonical renderer accepting the value and returning text.
    :param masked: Return the fixed masking marker without calling either renderer.
       Masking is independent of the length limit.
    :returns: CR/LF-escaped text, with any truncation marker included in the limit.
       Renderer failures, including BaseException and non-string results, become
       a stable failure description. No type label or task-local policy is added.
    :raises TypeError: If max_length is neither an integer nor None, including bool.
    :raises ValueError: If max_length is negative.
    """
    if max_length is not None:
        if isinstance(max_length, bool) or not isinstance(max_length, int):
            raise TypeError("representation length must be an integer or None")
        if max_length < 0:
            raise ValueError("representation length cannot be negative")
    if masked:
        return MASKED_VALUE
    try:
        rendered = repr(value) if renderer is None else renderer(value)
        if not isinstance(rendered, str):
            raise TypeError("representation renderer must return text")
        payload = str.__str__(rendered)
    except BaseException as error:
        payload = f"<repr failed: {type(error).__name__}>"
    payload = payload.replace("\r", "\\r").replace("\n", "\\n")
    if max_length is not None and len(payload) > max_length:
        marker = TRUNCATION_MARKER[:max_length]
        return payload[:max_length - len(marker)] + marker
    return payload
