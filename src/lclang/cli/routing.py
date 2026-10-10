"""Exact nested command-group routing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from lclang.cli.commands import Command, CommandGroup
from lclang.cli.parser import HELP_OPTIONS, VERSION_OPTIONS
from lclang.error import LclCliError, LclCliUsageError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_constructor, guard_failure
from lclang.error.codes.cli import Code as cli_codes


class RouteAction(Enum):
    """Distinguish execution, scoped help, and root version operations."""

    # Unitless route tags identify the three CLI dispatch outcomes; names keep command, help and
    # version handling separate.
    COMMAND = "command"
    HELP = "help"
    VERSION = "version"


@guard_constructor(LclValidationError, cli_codes.NATIVE_421)
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


@guard_constructor(LclValidationError, cli_codes.NATIVE_421)
class RouteFailure(LclCliUsageError):
    """Report routing failure with its nearest group scope."""

    def __init__(
        self, message: str, group: CommandGroup, path: tuple[str, ...], *, code: str | None = None
    ) -> None:
        """Create one nearest-scope routing failure.

        :param message: Human-readable routing problem.
        :param group: Nearest group whose help should render.
        :param path: Consumed path to that group.
        :param code: Classified routing cause.
        :returns: ``None``.
        """
        super().__init__(message, code=code)
        self.group = group
        self.path = path


@guard_failure(LclCliError, cli_codes.NATIVE_421)
def child_named(group: CommandGroup, name: str) -> Command | CommandGroup | None:
    """Return a group's exactly named child.

    :param group: Group to inspect.
    :param name: Case-sensitive child name.
    :returns: Matching child or ``None``.
    """
    return next((child for child in group.commands if child.name == name), None)


@guard_failure(LclCliError, cli_codes.NATIVE_421)
def route_command(root: CommandGroup, tokens: Sequence[str]) -> RouteResult:
    """Route post-script tokens through nested groups to a command.

    :param root: Descriptive root group not consumed from argv.
    :param tokens: Tokens beginning with an operation or child name.
    :returns: Immutable routing decision.
    :raises RouteFailure: If a command is missing, unknown, or malformed.
    """
    remaining = tuple(tokens)
    if not remaining:
        raise RouteFailure("missing command", root, (), code=cli_codes.E21_MISSING_COMMAND)
    if remaining[0] in HELP_OPTIONS:
        if len(remaining) != 1:
            raise RouteFailure(
                "help does not accept arguments",
                root,
                (),
                code=cli_codes.E21_HELP_DOES_NOT_ACCEPT_ARGUMENTS,
            )
        return RouteResult(RouteAction.HELP, root, None, (), ())
    if remaining[0] in VERSION_OPTIONS:
        if len(remaining) != 1:
            raise RouteFailure(
                "version does not accept arguments",
                root,
                (),
                code=cli_codes.E21_VERSION_DOES_NOT_ACCEPT_ARGUMENTS,
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
                    code=cli_codes.E21_HELP_DOES_NOT_ACCEPT_ARGUMENTS,
                )
            return RouteResult(RouteAction.HELP, group, None, path, ())
        child = child_named(group, token)
        if child is None:
            available = ", ".join(item.name for item in group.commands)
            message = f"unknown command: {token}; available: {available}"
            raise RouteFailure(message, group, path, code=cli_codes.E21_ROUTE_COMMAND_FAILURE)
        path = (*path, token)
        index += 1
        if isinstance(child, Command):
            return RouteResult(RouteAction.COMMAND, group, child, path, remaining[index:])
        group = child
    raise RouteFailure("missing command", group, path, code=cli_codes.E21_MISSING_COMMAND)
