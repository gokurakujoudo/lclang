"""Deterministic ANSI-free structured CLI help rendering."""

from __future__ import annotations

import inspect
import textwrap
from collections.abc import Iterable

from lclang.cli.commands import Command, CommandGroup
from lclang.cli.parameter_details import DerivedParameterDoc
from lclang.utils.representation import safe_repr

# Characters per line; the CLI layout contract fixes 100 for deterministic help
# across terminal sizes while leaving useful room for parameter descriptions.
HELP_WIDTH = 100
# Spaces; the help layout uses two to separate detail rows from section labels.
ROW_INDENT = 2
# Spaces; the help layout uses two to keep adjacent aligned columns distinguishable.
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
        ("--verbose", "Enable internal DEBUG and lower enabled logger output thresholds."),
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
    scopes: dict[str, list[tuple[str, str]]] = {}
    for parameter in sorted(
        command.parameter_docs,
        key=lambda item: (item.name.casefold(), item.name),
    ):
        type_name = inspect.formatannotation(parameter.value_type).replace("collections.abc.", "")
        has_default = parameter.default is not None or parameter.name in command.preset
        value = (
            parameter.default
            if parameter.default is not None
            else command.preset.get(parameter.name)
        )
        binding = command.default_bindings.get(
            parameter.name,
            command.default_bindings.get(parameter.name + "!"),
        )
        if binding is None and isinstance(parameter, DerivedParameterDoc):
            binding = parameter.help_default
        factory = False
        if not has_default and binding is not None:
            has_default = True
            value = binding.value
            factory = binding.factory is not None
        required = "required" if parameter.required and not has_default else "optional"
        default_value = safe_repr(
            value,
            masked=parameter.masked or parameter.name in command.masked_names,
        )
        if factory:
            default_value = "<factory>"
        default = f", default={default_value}" if has_default else ""
        detail = f"{type_name}; {required}{default}. {parameter.description}".strip()
        scope = parameter.name.rpartition(".")[0]
        scopes.setdefault(scope, []).append((parameter.name, detail))
    for scope in sorted(scopes, key=lambda name: (name.casefold(), name)):
        lines.extend(["", f"{scope or '(global)'}:", *format_rows(scopes[scope])])
    if not scopes:
        lines.append("  (none)")
    lines.extend(
        [
            "",
            "Logger configuration:",
            "  -o logger.console.level DEBUG",
            '  -o logger.file.default.enabled "LCL[False]"',
            '  -o logger.file.audit.enabled "LCL[True]"',
            "  logger.file.<sink> inherits missing fields from logger.file.default.",
            "  Explicit sink fields override the template; default never creates a file.",
        ]
    )
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
