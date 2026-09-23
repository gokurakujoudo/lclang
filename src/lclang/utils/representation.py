"""Safe single-line representations independent of runtime presentation state."""

from collections.abc import Callable, Iterable, Set
from dataclasses import fields, is_dataclass

from lclang.masking import MASKED_VALUE

# Unitless names identify this module's public downstream interface; helper constants stay local.
__all__ = ["make_multi_log_lines", "make_repr_lines", "safe_repr"]

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


def make_multi_log_lines(
    title: str, lines: Iterable[str], line_indent: str = "    ",
) -> str:
    """Join a title and indented body into one message.

    :param title: Unindented title, preserved verbatim.
    :param lines: Body elements, including empty elements and embedded newlines.
    :param line_indent: Prefix added to every physical body line.
    :returns: One message without an additional terminal newline.
    """
    body = (line_indent + line.replace("\n", "\n" + line_indent) for line in lines)
    return "\n".join([title, *body])


def align_repr_fields(
    items: Iterable[tuple[str, str]], key_column_length: int | None = None,
) -> list[str]:
    """Align previously represented values without inspecting the original objects.

    :param items: Ordered field names and protected value text.
    :param key_column_length: Optional nonnegative minimum key width in characters.
    :returns: Aligned name-colon-value lines retaining duplicate names.
    :raises TypeError: If the width is not an integer or None, including bool.
    :raises ValueError: If the width is negative.
    """
    if key_column_length is not None:
        if isinstance(key_column_length, bool) or not isinstance(key_column_length, int):
            raise TypeError("key column length must be an integer or None")
        if key_column_length < 0:
            raise ValueError("key column length cannot be negative")
    values = list(items)
    width = max((len(name) for name, _ in values), default=0)
    width = max(width, key_column_length or 0)
    return [f"{name.ljust(width)}: {value}" for name, value in values]


def make_repr_lines(
    instances: object, key_column_length: int | None = None,
    sort_keys: bool = False, masked_keys: Set[str] | None = None,
) -> list[str]:
    """Represent dataclass instances and dictionaries with pre-read masking.

    :param instances: One record or an iterable of records, consumed once.
    :param key_column_length: Optional nonnegative minimum field width in characters.
    :param sort_keys: Stably sort all fields by name rather than encounter order.
    :param masked_keys: Direct names redacted before reading or representing values.
    :returns: Aligned lines using safe_repr's default protections, without recursion.
    :raises TypeError: If a record, dictionary key or width has an unsupported type.
    :raises ValueError: If the minimum width is negative.
    :raises Exception: If an unmasked getter or input iterator fails.
    """
    align_repr_fields((), key_column_length)
    if is_dataclass(instances) or isinstance(instances, dict):
        records: Iterable[object] = (instances,)
    elif isinstance(instances, Iterable) and not isinstance(instances, (str, bytes)):
        records = instances
    else:
        raise TypeError("representations require dataclass instances or dictionaries")
    masked = frozenset() if masked_keys is None else masked_keys
    rendered: list[tuple[str, str]] = []
    for record in records:
        if isinstance(record, dict):
            names = list(record)
        elif is_dataclass(record) and not isinstance(record, type):
            names = [item.name for item in fields(record)]
        else:
            raise TypeError("representations require dataclass instances or dictionaries")
        for name in names:
            if not isinstance(name, str):
                raise TypeError("representation field names must be strings")
            if name in masked:
                value = None
            else:
                value = record[name] if isinstance(record, dict) else getattr(record, name)
            rendered.append((name, safe_repr(value, masked=name in masked)))
    if sort_keys:
        rendered.sort(key=lambda item: item[0])
    return align_repr_fields(rendered, key_column_length)
