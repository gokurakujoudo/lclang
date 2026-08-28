"""Deterministic ANSI-free structured CLI help rendering."""

from __future__ import annotations

import inspect
import textwrap
from collections.abc import Iterable

from lclang.cli.commands import Command, CommandGroup
from lclang.masking import MASKED_VALUE

# Fixed rendering width independent of terminal state.
HELP_WIDTH = 100
# Indentation for aligned help detail rows.
ROW_INDENT = 2
# Minimum gap between row labels and descriptions.
ROW_GAP = 2


def format_rows(rows: Iterable[tuple[str, str]]) -> list[str]:
    """Align and wrap label/description rows at the fixed help width.

    :param rows: Ordered label and description pairs.
    :returns: Rendered physical lines without trailing newlines.
    """
    values = tuple(rows)
    if not values:
        return []
    label_width = max(len(label) for label, _ in values)
    prefix_width = ROW_INDENT + label_width + ROW_GAP
    output: list[str] = []
    for label, description in values:
        wrapped = textwrap.wrap(description, width=max(20, HELP_WIDTH - prefix_width)) or [""]
        output.append(" " * ROW_INDENT + label.ljust(label_width) + " " * ROW_GAP + wrapped[0])
        output.extend(" " * prefix_width + line for line in wrapped[1:])
    return output


def common_option_rows() -> tuple[tuple[str, str], ...]:
    """Return canonical common command option help.

    :returns: Ordered option spelling and description pairs.
    """
    return (
        ("-c, --config <file>", "Load one .lclcfg configuration file."),
        (
            "-o, --override <key> [<value>]",
            "Override with a string, or True when omitted; repeatable and last value wins.",
        ),
        ("-a, --as-of <YYYYMMDD>", "Set the invocation date; defaults to today's local date."),
        ("-wif, --dryrun", "Tell the handler to avoid side effects when it supports dryrun."),
        ("--verbose", "Trace parsing, value provenance, and evaluation to stderr and logs."),
        ("-h, --help", "Show this command help."),
    )


def render_group_help(
    script: str,
    group: CommandGroup,
    path: tuple[str, ...],
    root: bool,
) -> str:
    """Render root or nested group help.

    :param script: Script display basename.
    :param group: Group whose children are listed.
    :param path: Consumed path excluding the root group.
    :param root: Whether version aliases apply.
    :returns: Structured help ending in one newline.
    """
    prefix = " ".join((script, *path))
    lines = [f"Usage: {prefix} <command> [options]", ""]
    if group.description:
        lines.extend(textwrap.wrap(group.description, HELP_WIDTH))
        lines.append("")
    lines.append("Commands:")
    rows = [
        (child.name, child.summary if isinstance(child, Command) else child.description)
        for child in group.commands
    ]
    lines.extend(format_rows(rows))
    lines.extend(["", "Options:", "  -h, --help     Show this help."])
    if root:
        lines.append("  -v, --version  Show the application version.")
    return "\n".join(lines) + "\n"


def render_command_help(script: str, command: Command, path: tuple[str, ...]) -> str:
    """Render one leaf command's options and configuration parameters.

    :param script: Script display basename.
    :param command: Selected leaf command.
    :param path: Full consumed nested command path.
    :returns: Structured help with A-Z parameter rows, ending in one newline.
    """
    prefix = " ".join((script, *path))
    lines = [f"Usage: {prefix} [options]", ""]
    if command.summary:
        lines.extend(textwrap.wrap(command.summary, HELP_WIDTH))
        lines.append("")
    lines.append("Configuration parameters:")
    parameter_rows: list[tuple[str, str]] = []
    for parameter in sorted(
        command.parameter_docs,
        key=lambda item: (item.name.casefold(), item.name),
    ):
        type_name = inspect.formatannotation(parameter.value_type)
        required = "required" if parameter.required else "optional"
        default_value = MASKED_VALUE if parameter.masked else repr(parameter.default)
        default = "" if parameter.default is None else f", default={default_value}"
        detail = f"{type_name}; {required}{default}. {parameter.description}".strip()
        parameter_rows.append((parameter.name, detail))
    lines.extend(format_rows(parameter_rows) or ["  (none)"])
    lines.extend(["", "Options:"])
    lines.extend(format_rows(common_option_rows()))
    return "\n".join(lines) + "\n"


def render_usage_error(message: str, help_text: str) -> str:
    """Prefix nearest-scope help with one concise error line.

    :param message: Human-readable usage problem.
    :param help_text: Already rendered nearest-scope help.
    :returns: Combined diagnostic ending in one newline.
    """
    return f"error: {message}\n\n{help_text}"
