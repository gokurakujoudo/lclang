"""Pure fixed-arity parsing for common CLI options.

Defines ``ParsedCommonOptions``, ``usage_error``, ``parse_common_options``,
``parse_cli_params``, ``help_requested``, ``lazy_override_expression``,
``override_expression``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from lclang.cli.argv_adapter import ArgvParts, split_argv
from lclang.cli.cli_models import CliParams
from lclang.cli.declaration_validation import require_lcl_qualified_name
from lclang.cli.invocation_key import CLI_RUNTIME_KEYS
from lclang.common.binding_mask import split_masked_name
from lclang.error import CliErrorCode, LclCliError, LclCliUsageError, LclSyntaxError
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure
from lclang.lang import parse_expression
from lclang.lang.ast import LclAstNode, LclConstant
from lclang.lang.stdlib.date_conversion import parse_ymd

# Common options consuming one following token.
# Unitless option spellings below are the public CLI grammar. Explicit aliases preserve existing
# short and long forms and let parsing distinguish valueless switches from options consuming
# arguments.
ONE_VALUE_OPTIONS = frozenset({"-c", "--config", "-a", "--as-of"})
# Override options consuming a key and an optional non-override value.
OVERRIDE_OPTIONS = frozenset({"-o", "--override"})
# Dryrun flag spellings.
DRYRUN_OPTIONS = frozenset({"-wif", "--dryrun"})
# Help flag spellings.
HELP_OPTIONS = frozenset({"-h", "--help"})
# Version flag spellings.
VERSION_OPTIONS = frozenset({"-v", "--version"})
# Verbose diagnostic flag spelling; ``-v`` remains the version alias.
VERBOSE_OPTIONS = frozenset({"--verbose"})


@guard_constructor(LclValidationError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class ParsedCommonOptions:
    """Retain pure intermediate common-option state.

    :param config_path: Optional raw config path.
    :param overrides: Right-biased raw strings or valueless ``True`` overrides.
    :param as_of_text: Optional raw compact date.
    :param dryrun: Parsed dryrun flag.
    :param help_requested: Whether help appeared at an option boundary.
    :param verbose: Whether internal diagnostic output was requested.
    :param masked_names: Immutable normalized override names marked for redaction.
    """

    config_path: str | None
    overrides: dict[str, str | bool]
    as_of_text: str | None
    dryrun: bool
    help_requested: bool
    verbose: bool
    masked_names: frozenset[str]


@guard_failure(LclCliError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
def usage_error(
    message: str, index: int, token: str, *, code: str | None = None
) -> LclCliUsageError:
    """Create one stable token-oriented usage failure.

    :param message: Human-readable problem.
    :param index: Zero-based index in the command option tail.
    :param code: Classified argument failure from the detecting branch.
    :param token: Responsible spelling.
    :returns: Structured CLI usage error.
    """
    return LclCliUsageError(f"{message} at argument {index}: {token}", code=code)


@guard_failure(LclCliError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
def parse_common_options(tokens: Sequence[str]) -> ParsedCommonOptions:
    """Parse common option tokens without constructing runtime values.

    :param tokens: Tokens following a selected command.
    :returns: Immutable intermediate parse result.
    :raises LclCliUsageError: If syntax, arity, duplication, or keys are invalid.
    """
    config_path: str | None = None
    as_of_text: str | None = None
    dryrun = False
    help_requested = False
    verbose = False
    overrides: dict[str, str | bool] = {}
    masked_names: set[str] = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in HELP_OPTIONS:
            help_requested = True
            index += 1
            continue
        if token in DRYRUN_OPTIONS:
            if dryrun:
                raise usage_error(
                    "duplicate dryrun option",
                    index,
                    token,
                    code=CliErrorCode.E31_DUPLICATE_DRYRUN_OPTION,
                )
            dryrun = True
            index += 1
            continue
        if token in VERBOSE_OPTIONS:
            if verbose:
                raise usage_error(
                    "duplicate verbose option",
                    index,
                    token,
                    code=CliErrorCode.E31_DUPLICATE_VERBOSE_OPTION,
                )
            verbose = True
            index += 1
            continue
        if token in ONE_VALUE_OPTIONS:
            if index + 1 >= len(tokens):
                raise usage_error(
                    "missing option value", index, token, code=CliErrorCode.E31_MISSING_OPTION
                )
            value = tokens[index + 1]
            if token in {"-c", "--config"}:
                if config_path is not None:
                    raise usage_error(
                        "duplicate config option",
                        index,
                        token,
                        code=CliErrorCode.E31_DUPLICATE_CONFIG_OPTION,
                    )
                config_path = value
            else:
                if as_of_text is not None:
                    raise usage_error(
                        "duplicate as-of option",
                        index,
                        token,
                        code=CliErrorCode.E31_DUPLICATE_AS_OF_OPTION,
                    )
                as_of_text = value
            index += 2
            continue
        if token in OVERRIDE_OPTIONS:
            if index + 1 >= len(tokens):
                raise usage_error(
                    "missing override key", index, token, code=CliErrorCode.E31_MISSING_OVERRIDE_KEY
                )
            raw_key = tokens[index + 1]
            try:
                key, masked = split_masked_name(raw_key)
                require_lcl_qualified_name(key, "override key")
            except LclValidationError as error:
                raise usage_error(error.message, index + 1, raw_key, code=error.code) from error
            if key.split(".", 1)[0] in CLI_RUNTIME_KEYS:
                raise usage_error(
                    "reserved override key",
                    index + 1,
                    key,
                    code=CliErrorCode.E31_RESERVED_OVERRIDE_KEY,
                )
            if masked:
                masked_names.add(key)
            value_index = index + 2
            if value_index >= len(tokens) or tokens[value_index] in OVERRIDE_OPTIONS:
                overrides[key] = True
                index += 2
                continue
            value = tokens[value_index]
            overrides[key] = value
            index += 3
            continue
        raise usage_error(
            "unknown option or argument",
            index,
            token,
            code=CliErrorCode.E31_UNKNOWN_OPTION_OR_ARGUMENT,
        )
    return ParsedCommonOptions(
        config_path,
        overrides,
        as_of_text,
        dryrun,
        help_requested,
        verbose,
        frozenset(masked_names),
    )


@guard_failure(LclCliError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
def parse_cli_params(
    parts: ArgvParts,
    command_path: Sequence[str],
    tokens: Sequence[str],
) -> CliParams:
    """Convert common options into immutable invocation parameters.

    :param parts: Validated full-argv partition.
    :param command_path: Routed nested command path.
    :param tokens: Common options following the command.
    :returns: Complete immutable CLI parameters.
    :raises LclCliUsageError: If date or common option parsing fails.
    """
    parsed = parse_common_options(tokens)
    try:
        as_of = date.today() if parsed.as_of_text is None else parse_ymd(parsed.as_of_text)
    except LclValidationError as error:
        raise LclCliUsageError(
            "invalid as-of date; expected YYYYMMDD",
            code=error.code,
        ) from error
    return CliParams(
        parts.executable_path,
        tuple(command_path),
        as_of,
        parsed.dryrun,
        parsed.config_path,
        parsed.overrides,
        parsed.verbose,
        masked_names=parsed.masked_names,
        script_path=parts.script_path,
        raw_argv=(parts.executable_path, parts.script_path, *parts.tokens),
    )


@guard_failure(LclCliError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
def help_requested(tokens: Sequence[str]) -> bool:
    """Report help at a valid fixed-arity option boundary.

    :param tokens: Common option tail.
    :returns: Whether help occurs outside another option's value slots.
    """
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in HELP_OPTIONS:
            return True
        if token in ONE_VALUE_OPTIONS:
            index += 2
        elif token in OVERRIDE_OPTIONS:
            value_index = index + 2
            if value_index >= len(tokens) or tokens[value_index] in OVERRIDE_OPTIONS:
                index += 2
            else:
                index += 3
        else:
            index += 1
    return False


@guard_failure(LclCliError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
def lazy_override_expression(value: str) -> LclAstNode | None:
    """Parse one complete valid lazy marker without creating a literal AST.

    :param value: Exact raw override token.
    :returns: Parsed marked expression when valid, otherwise ``None``.
    """
    if value.startswith("LCL[") and value.endswith("]"):
        body = value[4:-1]
        if body:
            try:
                return parse_expression(body)
            except LclSyntaxError, ValueError, LclValidationError:
                pass
    return None


@guard_failure(LclCliError, CliErrorCode.E31_OPTION_PARSING_NATIVE_FAILURE)
def override_expression(value: str) -> LclAstNode:
    """Convert one raw override into a lazy expression or literal constant.

    :param value: Exact raw override token.
    :returns: Parsed marked expression when valid, otherwise string constant.
    """
    expression = lazy_override_expression(value)
    if expression is not None:
        return expression
    return LclConstant(value=value)


# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "ArgvParts",
    "help_requested",
    "lazy_override_expression",
    "override_expression",
    "parse_cli_params",
    "split_argv",
]
