"""Exact nested command-group routing.

Defines ``RouteAction``, ``RouteResult``, ``child_named``, ``route_command``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from lclang.cli.command_definition import Command, CommandGroup
from lclang.cli.option_parser import HELP_OPTIONS, VERSION_OPTIONS
from lclang.error import CliErrorCode, LclCliError, RouteFailure
from lclang.error.exception_base import LclValidationError
from lclang.error.operation_guard import guard_constructor, guard_failure


class RouteAction(Enum):
    """Distinguish execution, scoped help, and root version operations."""

    # Unitless route tags identify the three CLI dispatch outcomes; names keep command, help and
    # version handling separate.
    COMMAND = "command"
    HELP = "help"
    VERSION = "version"


@guard_constructor(LclValidationError, CliErrorCode.E21_COMMAND_ROUTING_NATIVE_FAILURE)
@dataclass(frozen=True, slots=True)
class RouteResult:
    """Describe one exact routing decision.

    :param action: Selected routing operation.
    :param group: Nearest selected group.
    :param command: Selected leaf command, if any.
    :param path: Consumed nested path excluding the root group.
    :param remaining: Tokens left for command option parsing.
    """

    action: RouteAction
    group: CommandGroup
    command: Command | None
    path: tuple[str, ...]
    remaining: tuple[str, ...]


@guard_failure(LclCliError, CliErrorCode.E21_COMMAND_ROUTING_NATIVE_FAILURE)
def child_named(group: CommandGroup, name: str) -> Command | CommandGroup | None:
    """Return a group's exactly named child.

    :param group: Group to inspect.
    :param name: Case-sensitive child name.
    :returns: Matching child or ``None``.
    """
    return next((child for child in group.commands if child.name == name), None)


@guard_failure(LclCliError, CliErrorCode.E21_COMMAND_ROUTING_NATIVE_FAILURE)
def route_command(root: CommandGroup, tokens: Sequence[str]) -> RouteResult:
    """Route post-script tokens through nested groups to a command.

    :param root: Descriptive root group not consumed from argv.
    :param tokens: Tokens beginning with an operation or child name.
    :returns: Immutable routing decision.
    :raises RouteFailure: If a command is missing, unknown, or malformed.
    """
    remaining = tuple(tokens)
    if not remaining:
        raise RouteFailure("missing command", root, (), code=CliErrorCode.E21_MISSING_COMMAND)
    if remaining[0] in HELP_OPTIONS:
        if len(remaining) != 1:
            raise RouteFailure(
                "help does not accept arguments",
                root,
                (),
                code=CliErrorCode.E21_HELP_DOES_NOT_ACCEPT_ARGUMENTS,
            )
        return RouteResult(RouteAction.HELP, root, None, (), ())
    if remaining[0] in VERSION_OPTIONS:
        if len(remaining) != 1:
            raise RouteFailure(
                "version does not accept arguments",
                root,
                (),
                code=CliErrorCode.E21_VERSION_DOES_NOT_ACCEPT_ARGUMENTS,
            )
        return RouteResult(RouteAction.VERSION, root, None, (), ())
    group = root
    path: tuple[str, ...] = ()
    index = 0
    while index < len(remaining):
        token = remaining[index]
        if token in HELP_OPTIONS:
            if index != len(remaining) - 1:
                raise RouteFailure(
                    "help does not accept arguments",
                    group,
                    path,
                    code=CliErrorCode.E21_HELP_DOES_NOT_ACCEPT_ARGUMENTS,
                )
            return RouteResult(RouteAction.HELP, group, None, path, ())
        child = child_named(group, token)
        if child is None:
            available = ", ".join(item.name for item in group.commands)
            message = f"unknown command: {token}; available: {available}"
            raise RouteFailure(message, group, path, code=CliErrorCode.E21_ROUTE_COMMAND_FAILURE)
        path = (*path, token)
        index += 1
        if isinstance(child, Command):
            return RouteResult(RouteAction.COMMAND, group, child, path, remaining[index:])
        group = child
    raise RouteFailure("missing command", group, path, code=CliErrorCode.E21_MISSING_COMMAND)
