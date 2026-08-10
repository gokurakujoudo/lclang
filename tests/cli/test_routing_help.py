"""Behavioural tests for nested routing and structured help."""

import pytest

from lclang.cli import CliContext, CliResult, CliResultStatus, CommandGroup, ParameterDoc, cli
from lclang.cli.help import format_rows, render_command_help, render_group_help, render_usage_error
from lclang.cli.parser import split_argv
from lclang.cli.routing import RouteAction, RouteFailure, child_named, route_command


def make_group() -> CommandGroup:
    """Return a nested reusable routing fixture.

    :returns: Root command group with one nested command.
    """

    @cli.command(parameter_docs=[ParameterDoc("target", str, True, "Deployment target")])
    async def deploy_command(context: CliContext) -> CliResult:
        """Deploy configured assets.

        :param context: Current invocation.
        :returns: Successful result.
        """
        return CliResult(CliResultStatus.SUCCESS, "deployed")

    admin = CommandGroup("admin", "Admin", [deploy_command])
    return CommandGroup("root", "Example application", [admin])


def test_nested_route_and_help_scopes_are_exact() -> None:
    """The root is not consumed while nested groups contribute path segments."""
    root = make_group()
    parts = split_argv(["python", "tool.py", "admin", "deploy", "-h"])
    route = route_command(root, parts.tokens)
    assert route.action is RouteAction.COMMAND
    assert route.path == ("admin", "deploy")
    assert route.remaining == ("-h",)
    assert route.command is not None
    command_help = render_command_help("tool.py", route.command, route.path)
    assert "Configuration parameters" in command_help
    assert "target" in command_help
    assert "-o, --override <key> [<value>]" in command_help
    root_help = render_group_help("tool.py", root, (), True)
    assert "admin" in root_help
    assert "--version" in root_help


def test_root_group_and_version_actions_and_route_failures() -> None:
    """Every routing action and nearest-group failure branch is explicit."""
    root = make_group()
    assert route_command(root, ["-h"]).action is RouteAction.HELP
    assert route_command(root, ["--version"]).action is RouteAction.VERSION
    nested_help = route_command(root, ["admin", "--help"])
    assert nested_help.action is RouteAction.HELP
    assert nested_help.path == ("admin",)
    nested_text = render_group_help("tool.py", nested_help.group, nested_help.path, False)
    assert "Usage: tool.py admin" in nested_text
    assert "--version" not in nested_text
    assert child_named(root, "missing") is None
    for tokens, message in [
        ([], "missing"),
        (["--help", "extra"], "does not accept"),
        (["--version", "extra"], "does not accept"),
        (["admin"], "missing"),
        (["admin", "--help", "extra"], "does not accept"),
        (["unknown"], "unknown"),
    ]:
        with pytest.raises(RouteFailure, match=message):
            route_command(root, tokens)


def test_help_handles_empty_rows_and_wraps_usage_errors() -> None:
    """Empty groups and command descriptions render deterministically."""
    assert format_rows([]) == []
    empty = CommandGroup("root", "", [])
    help_text = render_group_help("tool.py", empty, (), True)
    assert "Commands:" in help_text
    combined = render_usage_error("bad", help_text)
    assert combined.startswith("error: bad\n\nUsage:")

    @cli.command(summary="")
    async def empty_command(context: CliContext) -> CliResult:
        """Return empty help metadata.

        :param context: Current invocation.
        :returns: Successful result.
        """
        return CliResult(CliResultStatus.SUCCESS, "")

    command_help = render_command_help("tool.py", empty_command, ("empty",))
    assert "(none)" in command_help
