"""Parser for version metadata, colon definitions, and using declarations."""

from __future__ import annotations

from pathlib import Path

from lclang.config.declarations import (
    following_boundary,
    parse_using,
    parse_version,
    validate_definition_name,
)
from lclang.config.expressions import parse_config_expression
from lclang.config.imports import parse_import
from lclang.config.lines import LogicalLine, scan_logical_lines
from lclang.config.model import ConfigDeclaration, ConfigDefinition, ConfigDocument
from lclang.config.positions import advance_position
from lclang.diagnostics import internal_masked_scope
from lclang.error import LclConfigError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_failure
from lclang.error.codes.configuration import Code as configuration_codes
from lclang.error.configuration import LclConfigSyntaxError, LclConfigVersionError
from lclang.masking import split_masked_name
from lclang.source import SourceOrigin
from lclang.types import SourceName, VarName


@guard_failure(LclConfigError, configuration_codes.NATIVE_311)
def parse_config(
    text: str,
    *,
    source_name: str = "<memory>",
    source_path: str | Path | None = None,
) -> ConfigDocument:
    """Parse one unresolved Unicode configuration source.

    :param text: Complete `.lclcfg` source text.
    :param source_name: Non-empty diagnostic display name.
    :param source_path: Optional physical path enabling eager file magic.
    :returns: Immutable source-ordered configuration document.
    :raises LclValidationError: If arguments have unsupported public types.
    :raises LclValidationError: If the source name is empty.
    :raises LclConfigSyntaxError: If declarations or expressions are malformed.
    :raises LclConfigVersionError: If version metadata is invalid.

    .. note::
       Supplying a path enables magic but never causes file I/O.
    """
    if not isinstance(text, str):
        raise LclValidationError(
            "config text must be a string",
            code=configuration_codes.E11_CONFIG_TEXT_MUST_BE_A_STRING,
        )
    if not isinstance(source_name, str):
        raise LclValidationError(
            "config source name must be a string",
            code=configuration_codes.E11_CONFIG_TEXT_MUST_BE_A_STRING,
        )
    if not source_name:
        raise LclValidationError(
            "config source name cannot be empty",
            code=configuration_codes.E11_CONFIG_SOURCE_NAME_CANNOT_BE_EMPTY,
        )
    path = normalize_source_path(source_path)
    origin = SourceOrigin(SourceName(source_name), path)
    return parse_document(text, origin)


@guard_failure(LclConfigError, configuration_codes.NATIVE_311)
def parse_document(text: str, origin: SourceOrigin) -> ConfigDocument:
    """Parse text whose final origin was already selected by a loader.

    :param text: Complete Unicode configuration text.
    :param origin: Stable physical or synthetic origin.
    :returns: Immutable parsed document.
    :raises LclConfigSyntaxError: If any declaration is malformed.
    :raises LclConfigVersionError: If metadata is late or unsupported.

    .. note::
       Duplicate definitions remain ordered declarations for expansion.
    """
    declarations: list[ConfigDeclaration] = []
    version = 1
    meaningful_seen = False
    version_seen = False
    for line in scan_logical_lines(text, origin):
        stripped = line.text.lstrip(" \t\f")
        leading = len(line.text) - len(stripped)
        if stripped.startswith("__LCL_VERSION__"):
            if meaningful_seen or version_seen:
                raise LclConfigVersionError(
                    "version metadata must be first",
                    span=line.span,
                    code=configuration_codes.E11_VERSION_METADATA_MUST_BE_FIRST,
                )
            version = parse_version(line, leading, origin)
            version_seen = True
            meaningful_seen = True
            continue
        meaningful_seen = True
        using_end = 6 if stripped.startswith("using?") else 5
        import_end = 7 if stripped.startswith("import?") else 6
        if stripped.startswith("using") and following_boundary(stripped, using_end):
            declarations.append(parse_using(line, leading, len(declarations), origin))
        elif stripped.startswith("import") and following_boundary(stripped, import_end):
            declarations.append(parse_import(line, leading, len(declarations), origin))
        else:
            declarations.append(parse_definition(line, leading, len(declarations), origin))
    return ConfigDocument(origin, version, tuple(declarations))


@guard_failure(LclConfigError, configuration_codes.NATIVE_311)
def parse_definition(
    line: LogicalLine,
    leading: int,
    ordinal: int,
    origin: SourceOrigin,
) -> ConfigDefinition:
    """Parse one colon definition and its complete LCL expression.

    :param line: Logical declaration text and span.
    :param leading: Horizontal indentation before the name.
    :param ordinal: Declaration position in the document.
    :param origin: Owning source origin.
    :returns: Immutable parsed definition.
    :raises LclConfigSyntaxError: If name, separator, or expression is invalid.

    .. note::
       The first colon separates the already-validated binding from its RHS.
    """
    first_line = line.text.splitlines(keepends=False)[0]
    colon = first_line.find(":", leading)
    if colon < 0:
        raise LclConfigSyntaxError(
            "definition requires colon",
            span=line.span,
            code=configuration_codes.E11_DEFINITION_REQUIRES_COLON,
        )
    raw_name = first_line[leading:colon].strip(" \t\f")
    try:
        name, masked = split_masked_name(raw_name)
    except LclValidationError as error:
        raise LclConfigSyntaxError(
            "invalid config definition name",
            span=line.span,
            code=error.code,
        ) from error
    validate_definition_name(name, line, origin)
    expression_text = line.text[colon + 1 :]
    if not expression_text.strip():
        raise LclConfigSyntaxError(
            "definition requires an expression",
            span=line.span,
            code=configuration_codes.E11_DEFINITION_REQUIRES_AN_EXPRESSION,
        )
    start = advance_position(line.start, line.text[: colon + 1])
    with internal_masked_scope(masked):
        expression = parse_config_expression(
            expression_text, origin=origin, start=start, snapshot=line.span.snapshot
        )
    return ConfigDefinition(VarName(name), expression, line.span, ordinal, masked)


@guard_failure(LclConfigError, configuration_codes.NATIVE_311)
def normalize_source_path(source_path: str | Path | None) -> Path | None:
    """Normalize optional file-backed parsing identity without reading it.

    :param source_path: Optional path-like public argument.
    :returns: Canonical absolute path or ``None``.
    :raises LclValidationError: If the argument is not text or a Path.
    :raises LclValidationError: If its suffix is not exactly `.lclcfg`.

    .. note::
       Canonicalization uses non-strict resolution and performs no read.
    """
    if source_path is None:
        return None
    if not isinstance(source_path, (str, Path)):
        raise LclValidationError(
            "config source path must be text or Path",
            code=configuration_codes.E11_CONFIG_TEXT_MUST_BE_A_STRING,
        )
    path = Path(source_path).resolve(strict=False)
    if path.suffix != ".lclcfg":
        raise LclValidationError(
            "config source path must end in .lclcfg",
            code=configuration_codes.E11_CONFIG_SOURCE_PATH_MUST_END_IN_LCLCFG,
        )
    return path
