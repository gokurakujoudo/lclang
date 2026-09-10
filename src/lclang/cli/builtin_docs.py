"""Deterministic descriptions and rendering for canonical LCL builtins."""

from collections.abc import Mapping
from types import MappingProxyType

from lclang.api import LCL_BUILTIN_VALUES
from lclang.stdlib import STANDARD_MANIFESTS
from lclang.utils.calendar.lcl import CALENDARS_NAMESPACE

# Stable descriptions for values in the canonical builtin Frame.
# Unitless help descriptions below describe the reviewed public builtin inventory. These
# authored summaries supply deterministic help text where raw Python docstrings would expose
# inconsistent or overly broad contracts.
BUILTIN_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {
        "SnowflakeGenerator": "Create a Snowflake ID generator for an assigned worker.",
        "abs": "Return the absolute value.",
        "all": "Test whether all items are truthy.",
        "any": "Test whether any item is truthy.",
        "bin": "Format an integer in binary.",
        "bool": "Convert a value to Boolean.",
        "bytes": "Create immutable bytes.",
        "chr": "Convert a code point to a Unicode character.",
        "dict": "Create a dictionary.",
        "divmod": "Return a quotient and remainder pair.",
        "enumerate": "Pair items with consecutive indexes.",
        "env": "Read live process environment variables with scoped overrides.",
        "filter": "Keep items accepted by a predicate.",
        "float": "Convert a value to a floating-point number.",
        "format": "Format a value with a format specification.",
        "frozenset": "Create an immutable set.",
        "hex": "Format an integer in hexadecimal.",
        "int": "Convert a value to an integer.",
        "isinstance": "Test whether a value has a selected type.",
        "len": "Return the number of items.",
        "list": "Create a list.",
        "map": "Apply a function to corresponding items.",
        "max": "Return the greatest item.",
        "min": "Return the least item.",
        "oct": "Format an integer in octal.",
        "ord": "Return the code point of a Unicode character.",
        "parse_ymd": "Parse a strict YYYYMMDD date.",
        "pow": "Raise a value to a power, optionally modulo a value.",
        "range": "Create an arithmetic integer range.",
        "recursive": "Build a variadic eager fixed point.",
        "repr": "Return the Python representation of a value.",
        "reversed": "Iterate over a sequence in reverse.",
        "round": "Round a number to a selected precision.",
        "set": "Create a set.",
        "slice": "Create a slice descriptor.",
        "sorted": "Return a newly sorted list.",
        "str": "Convert a value to text.",
        "sum": "Sum items from a starting value.",
        "to_ymd": "Format a date as strict YYYYMMDD text.",
        "use_calendar_manager": "Create a named business-day calendar manager.",
        "use_file_system_hardcoded_calendar_loader": (
            "Create a strict JSON business-day calendar loader."
        ),
        "tuple": "Create an immutable tuple.",
        "zip": "Group corresponding items from iterables.",
    }
)

# Stable descriptions for ordinary functions in the root builtin Frame.
ROOT_BUILTIN_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {"lhs": "Return the active definition name."}
)

# Stable descriptions for reviewed root builtin namespaces.
NAMESPACE_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {
        "data": "Read-only mapping helpers.",
        "iter": "Synchronous and asynchronous iterable helpers.",
        "json": "Strict JSON encoding and decoding helpers.",
        "text": "Unicode text helpers.",
        "calendars": "Business-day calendar construction and singleton values.",
    }
)

# Stable descriptions for members of the reviewed calendar namespace.
CALENDAR_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {name: "Business-day calendar value or constructor." for name in CALENDARS_NAMESPACE}
)


def render_builtin_docs() -> str:
    """Render the complete canonical builtin inventory.

    :returns: Deterministic newline-joined top-level and nested documentation.
    :raises ValueError: If description metadata drifts or public names collide.

    .. note::
       Namespace methods retain manifest declaration order beneath globally
       sorted top-level names.
    """
    manifests = {item.namespace: item for item in STANDARD_MANIFESTS}
    if set(NAMESPACE_DESCRIPTIONS) != {*manifests, "calendars"}:
        raise ValueError("namespace descriptions do not match canonical values")
    expected_values = {*BUILTIN_DESCRIPTIONS, *NAMESPACE_DESCRIPTIONS}
    if expected_values != set(LCL_BUILTIN_VALUES):
        raise ValueError("builtin descriptions do not match canonical values")
    if set(CALENDAR_DESCRIPTIONS) != set(CALENDARS_NAMESPACE):
        raise ValueError("calendar descriptions do not match canonical values")
    groups = (
        tuple(BUILTIN_DESCRIPTIONS),
        tuple(ROOT_BUILTIN_DESCRIPTIONS),
        tuple(NAMESPACE_DESCRIPTIONS),
    )
    names = tuple(name for group in groups for name in group)
    if len(names) != len(set(names)):
        raise ValueError("canonical builtin names must be unique")
    descriptions = (
        *BUILTIN_DESCRIPTIONS.values(),
        *ROOT_BUILTIN_DESCRIPTIONS.values(),
        *NAMESPACE_DESCRIPTIONS.values(),
        *CALENDAR_DESCRIPTIONS.values(),
    )
    if any(not value.strip() or value != value.strip() for value in descriptions):
        raise ValueError("builtin descriptions must be non-blank and trimmed")
    if any("\n" in value or "\r" in value for value in descriptions):
        raise ValueError("builtin descriptions must occupy one line")

    lines: list[str] = []
    for name in sorted(names):
        if name in BUILTIN_DESCRIPTIONS:
            lines.append(f"- {name}: {BUILTIN_DESCRIPTIONS[name]}")
        elif name in ROOT_BUILTIN_DESCRIPTIONS:
            lines.append(f"- {name}: {ROOT_BUILTIN_DESCRIPTIONS[name]}")
        else:
            lines.append(f"- {name}: {NAMESPACE_DESCRIPTIONS[name]}")
            if name == "calendars":
                lines.extend(
                    f"  - {member}: {CALENDAR_DESCRIPTIONS[member]}"
                    for member in CALENDARS_NAMESPACE
                )
            else:
                lines.extend(
                    f"  - {entry.name}: {entry.summary}" for entry in manifests[name].entries
                )
    return "\n".join(lines)
