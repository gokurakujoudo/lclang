"""Exact nested command-group routing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from lclang.cli.commands import Command, CommandGroup
from lclang.cli.parser import HELP_OPTIONS, VERSION_OPTIONS
from lclang.errors import LclCliUsageError


class RouteAction(Enum):
    """Distinguish execution, scoped help, and root version operations."""

    COMMAND = "command"
    HELP = "help"
    VERSION = "version"


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


class RouteFailure(LclCliUsageError):
    """Report routing failure with its nearest group scope."""

    def __init__(self, message: str, group: CommandGroup, path: tuple[str, ...]) -> None:
        """Create one nearest-scope routing failure.

        :param message: Human-readable routing problem.
        :param group: Nearest group whose help should render.
        :param path: Consumed path to that group.
        :returns: ``None``.
        """
        super().__init__(message)
        self.group = group
        self.path = path


def child_named(group: CommandGroup, name: str) -> Command | CommandGroup | None:
    """Return a group's exactly named child.

    :param group: Group to inspect.
    :param name: Case-sensitive child name.
    :returns: Matching child or ``None``.
    """
    return next((child for child in group.commands if child.name == name), None)


def route_command(root: CommandGroup, tokens: Sequence[str]) -> RouteResult:
    """Route post-script tokens through nested groups to a command.

    :param root: Descriptive root group not consumed from argv.
    :param tokens: Tokens beginning with an operation or child name.
    :returns: Immutable routing decision.
    :raises RouteFailure: If a command is missing, unknown, or malformed.
    """
    remaining = tuple(tokens)
    if not remaining:
        raise RouteFailure("missing command", root, ())
    if remaining[0] in HELP_OPTIONS:
        if len(remaining) != 1:
            raise RouteFailure("help does not accept arguments", root, ())
        return RouteResult(RouteAction.HELP, root, None, (), ())
    if remaining[0] in VERSION_OPTIONS:
        if len(remaining) != 1:
            raise RouteFailure("version does not accept arguments", root, ())
        return RouteResult(RouteAction.VERSION, root, None, (), ())
    group = root
    path: tuple[str, ...] = ()
    index = 0
    while index < len(remaining):
        token = remaining[index]
        if token in HELP_OPTIONS:
            if index != len(remaining) - 1:
                raise RouteFailure("help does not accept arguments", group, path)
            return RouteResult(RouteAction.HELP, group, None, path, ())
        child = child_named(group, token)
        if child is None:
            available = ", ".join(item.name for item in group.commands)
            message = f"unknown command: {token}; available: {available}"
            raise RouteFailure(message, group, path)
        path = (*path, token)
        index += 1
        if isinstance(child, Command):
            return RouteResult(RouteAction.COMMAND, group, child, path, remaining[index:])
        group = child
    raise RouteFailure("missing command", group, path)
