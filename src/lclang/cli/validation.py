"""Shared validation helpers for CLI declarations and values."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

from lclang.ast import LclName
from lclang.cli.runtime_keys import CLI_RUNTIME_KEYS
from lclang.errors import LclSyntaxError
from lclang.lang import parse_expression
from lclang.scopes import validate_qualified_name

# Scoped names used to resolve effective logger configuration.
LOG_NAMES = frozenset(
    {
        "logger",
        "logger.log_dir",
        "logger.log_file_name",
        "logger.log_level",
        "logger.log_format",
    }
)
# Names unavailable to command parameter declarations and presets.
DECLARATION_RESERVED_NAMES = CLI_RUNTIME_KEYS | LOG_NAMES
# Complete grammar for literal command and command-group segments.
COMMAND_SEGMENT_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


def normalize_text(value: str, field: str) -> str:
    """Collapse Unicode whitespace for one descriptive field.

    :param value: Text supplied by a caller.
    :param field: Field label used in diagnostics.
    :returns: Single-line normalized text.
    :raises TypeError: If *value* is not text.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field} must be text")
    return " ".join(value.split())


def is_lcl_identifier(value: object) -> bool:
    """Report whether a value is one complete LCL identifier.

    :param value: Candidate value.
    :returns: Whether parsing selects exactly an identifier node.
    """
    if not isinstance(value, str) or not value:
        return False
    try:
        return isinstance(parse_expression(value), LclName)
    except LclSyntaxError, ValueError:
        return False


def require_lcl_identifier(value: object, field: str) -> str:
    """Return a validated LCL identifier.

    :param value: Candidate identifier.
    :param field: Field label used in diagnostics.
    :returns: Validated identifier text.
    :raises ValueError: If *value* is not a complete LCL identifier.
    """
    if not is_lcl_identifier(value):
        raise ValueError(f"{field} must be a valid LCL identifier")
    return str(value)


def require_lcl_qualified_name(value: object, field: str) -> str:
    """Return one validated dot-separated LCL name.

    :param value: Candidate qualified binding name.
    :param field: Field label used in diagnostics.
    :returns: Validated text.
    :raises ValueError: If any path segment is invalid.
    """
    try:
        validate_qualified_name(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must contain valid LCL identifiers") from error
    return str(value)


def require_command_segment(value: object, field: str) -> str:
    """Return a validated literal snake_case command segment.

    :param value: Candidate command or group name.
    :param field: Field label used in diagnostics.
    :returns: Validated command segment.
    :raises ValueError: If *value* is outside the CLI segment grammar.
    """
    if not isinstance(value, str) or COMMAND_SEGMENT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be lowercase ASCII snake_case")
    return value


def freeze_mapping[ValueT](
    values: Mapping[str, ValueT],
    field: str,
) -> Mapping[str, ValueT]:
    """Detach and expose a read-only string-keyed mapping.

    :param values: Mapping supplied by a caller.
    :param field: Field label used in diagnostics.
    :returns: Read-only detached mapping.
    :raises TypeError: If *values* or one key has the wrong type.
    """
    if not isinstance(values, Mapping):
        raise TypeError(f"{field} must be a mapping")
    snapshot = dict(values)
    if any(not isinstance(key, str) for key in snapshot):
        raise TypeError(f"{field} names must be strings")
    return MappingProxyType(snapshot)
