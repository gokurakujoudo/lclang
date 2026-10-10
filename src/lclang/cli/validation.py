"""Shared validation helpers for CLI declarations and values."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

from lclang.ast import LclName
from lclang.cli.runtime_keys import CLI_RUNTIME_KEYS
from lclang.error import LclCliError, LclSyntaxError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.cli import Code as cli_codes
from lclang.lang import parse_expression
from lclang.scopes import validate_qualified_name

# Scoped names used to resolve effective logger configuration.
# Unitless names and the command-segment expression below implement the public CLI grammar.
# Logger and runtime keys are protected from declaration collisions; lowercase snake_case
# segments keep routing unambiguous.
LOG_NAMES = frozenset({"logger"})
# Names unavailable to command parameter declarations and presets.
DECLARATION_RESERVED_NAMES = CLI_RUNTIME_KEYS | LOG_NAMES
# Complete grammar for literal command and command-group segments.
COMMAND_SEGMENT_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


@guard_failure(LclCliError, cli_codes.NATIVE_413)
def normalize_text(value: str, field: str) -> str:
    """Collapse Unicode whitespace for one descriptive field.

    :param value: Text supplied by a caller.
    :param field: Field label used in diagnostics.
    :returns: Single-line normalized text.
    :raises LclValidationError: If *value* is not text.
    """
    if not isinstance(value, str):
        raise LclValidationError(f"{field} must be text", code=cli_codes.E13_VALUE_MUST_BE_TEXT)
    return " ".join(value.split())


@guard_failure(LclCliError, cli_codes.NATIVE_413)
def is_lcl_identifier(value: object) -> bool:
    """Report whether a value is one complete LCL identifier.

    :param value: Candidate value.
    :returns: Whether parsing selects exactly an identifier node.
    """
    if not isinstance(value, str) or not value:
        return False
    try:
        return isinstance(parse_expression(value), LclName)
    except LclSyntaxError, ValueError, LclValidationError:
        return False


@guard_failure(LclCliError, cli_codes.NATIVE_413)
def require_lcl_qualified_name(value: object, field: str) -> str:
    """Return one validated dot-separated LCL name.

    :param value: Candidate qualified binding name.
    :param field: Field label used in diagnostics.
    :returns: Validated text.
    :raises LclValidationError: If any path segment is invalid.
    """
    try:
        validate_qualified_name(value)  # type: ignore[arg-type]
    except LclValidationError as error:
        raise LclValidationError(
            f"{field} must contain valid LCL identifiers",
            code=error.code,
        ) from error
    return str(value)


@guard_failure(LclCliError, cli_codes.NATIVE_413)
def require_command_segment(value: object, field: str) -> str:
    """Return a validated literal snake_case command segment.

    :param value: Candidate command or group name.
    :param field: Field label used in diagnostics.
    :returns: Validated command segment.
    :raises LclValidationError: If *value* is outside the CLI segment grammar.
    """
    if not isinstance(value, str) or COMMAND_SEGMENT_PATTERN.fullmatch(value) is None:
        raise LclValidationError(
            f"{field} must be lowercase ASCII snake_case",
            code=cli_codes.E13_VALUE_MUST_BE_LOWERCASE_ASCII_SNAKE_CASE,
        )
    return value


@guard_failure(LclCliError, cli_codes.NATIVE_413)
def freeze_mapping[ValueT](
    values: Mapping[str, ValueT],
    field: str,
) -> Mapping[str, ValueT]:
    """Detach and expose a read-only string-keyed mapping.

    :param values: Mapping supplied by a caller.
    :param field: Field label used in diagnostics.
    :returns: Read-only detached mapping.
    :raises LclValidationError: If *values* or one key has the wrong type.
    """
    if not isinstance(values, Mapping):
        raise LclValidationError(
            f"{field} must be a mapping", code=cli_codes.E13_VALUE_MUST_BE_A_MAPPING
        )
    snapshot = dict(values)
    if any(not isinstance(key, str) for key in snapshot):
        raise LclValidationError(
            f"{field} names must be strings", code=cli_codes.E13_VALUE_MUST_BE_TEXT
        )
    return MappingProxyType(snapshot)
