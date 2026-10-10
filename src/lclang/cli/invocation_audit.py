"""Readable non-evaluating CLI audit rendering.

Defines ``redacted_overrides``, ``canonical_argv``, ``normalized_argv``,
``selected_binding``, ``execution_config``, ``execution_banner``, ``emit_execution_start``.
"""

from __future__ import annotations

import json
import logging

from lclang.cli.cli_models import CliParams
from lclang.cli.option_parser import OVERRIDE_OPTIONS
from lclang.common.binding_mask import MASKED_VALUE, split_masked_name
from lclang.error import CliErrorCode, LclCliError
from lclang.error.operation_guard import guard_failure
from lclang.error.verbose_diagnostic import internal_render_value
from lclang.lang.engine.printer import to_source
from lclang.lang.runtime import Frame
from lclang.lang.runtime.frame.binding_lookup import find_scoped_binding
from lclang.logger import Logger
from lclang.logger.record_formatter import FILE_ONLY_ATTRIBUTE

# Characters; the existing execution-banner layout fixes 51 for compact centered
# headings independent of the terminal width.
EXECUTION_BANNER_WIDTH = 51
# Characters; subtract both two-character borders from the chosen banner width.
EXECUTION_BANNER_INTERIOR = EXECUTION_BANNER_WIDTH - 4
# LogRecord attribute marking mandatory CLI audit preamble records.
AUDIT_RECORD_ATTRIBUTE = "lclang_audit_record"


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def redacted_overrides(params: CliParams, frame: Frame) -> dict[str, str | bool]:
    """Return invocation overrides with exact-name secrets hidden.

    :param params: Parsed invocation values.
    :param frame: Effective invocation Frame carrying sticky mask metadata.
    :returns: Fresh override mapping safe for lclang-owned audit logs.
    """
    return {
        name: MASKED_VALUE if frame.is_masked(name) else value
        for name, value in params.overrides.items()
    }


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def canonical_argv(params: CliParams, frame: Frame) -> list[str]:
    """Build deterministic argv when exact original tokens are unavailable.

    :param params: Parsed invocation values.
    :param frame: Effective invocation Frame carrying sticky mask metadata.
    :returns: Canonical redacted argv tokens.
    """
    values = [params.executable_path, params.script_path, *params.command]
    if params.config_file_path is not None:
        values.extend(("--config", params.config_file_path))
    safe_overrides = redacted_overrides(params, frame)
    for name, value in safe_overrides.items():
        values.extend(("--override", name))
        if params.overrides[name] is not True:
            values.append(str(value))
    values.extend(("--as-of", params.as_of_date.strftime("%Y%m%d")))
    if params.dryrun:
        values.append("--dryrun")
    if params.verbose:
        values.append("--verbose")
    return values


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def normalized_argv(params: CliParams, frame: Frame) -> list[str]:
    """Return exact-order argv with masked override values redacted.

    :param params: Parsed invocation values.
    :param frame: Effective invocation Frame carrying sticky mask metadata.
    :returns: Redacted original tokens or a canonical fallback.
    """
    if params.raw_argv is None:
        return canonical_argv(params, frame)
    values = list(params.raw_argv)
    index = 0
    while index < len(values):
        if values[index] not in OVERRIDE_OPTIONS or index + 1 >= len(values):
            index += 1
            continue
        name, _ = split_masked_name(values[index + 1])
        value_index = index + 2
        if value_index < len(values) and values[value_index] not in OVERRIDE_OPTIONS:
            if frame.is_masked(name):
                values[value_index] = MASKED_VALUE
            index += 3
        else:
            index += 2
    return values


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def selected_binding(frame: Frame, name: str) -> str | None:
    """Render one selected binding without evaluating it.

    :param frame: Effective invocation Frame.
    :param name: Candidate command or configuration name.
    :returns: Definition source, typed host value, or ``None`` when absent.
    """
    owner, kind = find_scoped_binding(frame, name)
    if owner is None or kind == "proxy":
        return None
    masked = frame.is_masked(name)
    if name in owner.module.definitions:
        return MASKED_VALUE if masked else to_source(owner.module.definitions[name])
    value = owner.values[name]
    if masked:
        return f"({type(value).__name__}) {MASKED_VALUE}"
    return internal_render_value(value)


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def execution_config(frame: Frame, names: tuple[str, ...]) -> str:
    """Render aligned winner-only command and file configuration.

    :param frame: Effective invocation Frame.
    :param names: Sorted candidate audit names.
    :returns: One multi-line execution configuration record.
    """
    winners = [(name, selected_binding(frame, name)) for name in names]
    selected = [(name, value) for name, value in winners if value is not None]
    if not selected:
        return "execution config:"
    width = max(len(name) for name, _ in selected)
    rows = [f"    {name.ljust(width)}: {value}" for name, value in selected]
    return "execution config:\n" + "\n".join(rows)


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def execution_banner(params: CliParams) -> str:
    """Render the fixed-width centered invocation banner.

    :param params: Parsed invocation values.
    :returns: Multi-line banner following the audit heading.
    """
    border = "=" * EXECUTION_BANNER_WIDTH
    command = ".".join(params.command)
    values = (
        command,
        f"As-of Date: {params.as_of_date.isoformat()}",
        f"Dryrun Mode: {'ON' if params.dryrun else 'OFF'}",
        f"Verbose Mode: {'ON' if params.verbose else 'OFF'}",
    )
    rows = [f"=={value.center(EXECUTION_BANNER_INTERIOR)}==" for value in values]
    return "execution started:\n" + "\n".join((border, *rows, border))


@guard_failure(LclCliError, CliErrorCode.E51_COMMAND_EXECUTION_NATIVE_FAILURE)
def emit_execution_start(
    logger: logging.Logger | Logger,
    params: CliParams,
    frame: Frame,
    names: tuple[str, ...],
) -> None:
    """Write the execution banner, redacted argv and lazy configuration.

    :param logger: Invocation logger receiving audit records.
    :param params: Parsed invocation values.
    :param frame: Effective invocation Frame.
    :param names: Candidate execution configuration names.
    """
    extra = {AUDIT_RECORD_ATTRIBUTE: True, FILE_ONLY_ATTRIBUTE: True}
    logger.info(execution_banner(params), extra=extra)
    argv = json.dumps(normalized_argv(params, frame), ensure_ascii=False)
    logger.info(f"execution command line: {argv}", extra=extra)
    logger.info(execution_config(frame, names), extra=extra)
