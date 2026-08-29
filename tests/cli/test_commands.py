"""Behavioural tests for command declarations and groups."""

from datetime import date
from typing import Any, cast

import pytest

from lclang.cli import (
    RUNTIME_DRYRUN_KEY,
    CliContext,
    CliResult,
    CliResultStatus,
    Command,
    CommandGroup,
    ParameterDoc,
    cli,
)

InvalidCommand = cast(Any, Command)
InvalidCommandGroup = cast(Any, CommandGroup)


def test_decorator_builds_a_command_from_exact_async_handler() -> None:
    """Default metadata comes from the handler name and rST prose."""

    @cli.command(parameter_docs=[ParameterDoc("value", str, True, "Configured value")])
    async def sample_command(context: CliContext) -> CliResult:
        """Run the sample command.

        :param context: Current invocation.
        :returns: Successful result.
        """
        assert context.as_of_date == date(2026, 8, 9)
        return CliResult(CliResultStatus.SUCCESS, "ok")

    assert isinstance(sample_command, Command)
    assert sample_command.name == "sample"
    assert sample_command.summary == "Run the sample command."
    assert sample_command.parameter_docs[0].name == "value"


def test_groups_snapshot_children_and_reject_collisions() -> None:
    """Nested declarations preserve order without accepting ambiguous siblings."""

    @cli.command(summary="first")
    async def first_command(context: CliContext) -> CliResult:
        """Run first.

        :param context: Current invocation.
        :returns: Successful result.
        """
        return CliResult(CliResultStatus.SUCCESS, "")

    children = [first_command]
    group = CommandGroup("root", "Root tools", children)
    children.clear()
    assert group.commands == (first_command,)
    with pytest.raises(ValueError, match="duplicate"):
        CommandGroup("root", "Root tools", [first_command, first_command])


def test_decorator_rejects_non_async_or_wrong_annotations() -> None:
    """Incompatible handlers fail during declaration rather than execution."""
    with pytest.raises(TypeError, match="async"):

        @cli.command()  # type: ignore[arg-type]
        def invalid_command(context: CliContext) -> CliResult:
            """Return an unreachable result.

            :param context: Current invocation.
            :returns: Unreachable result.
            """
            return CliResult(CliResultStatus.SUCCESS, "")


async def valid_handler(context: CliContext) -> CliResult:
    """Return a reusable valid result.

    :param context: Current invocation.
    :returns: Successful result.
    """
    return CliResult(CliResultStatus.SUCCESS, str(context.dryrun))


@pytest.mark.parametrize(
    "factory, message",
    [
        (lambda: Command("Bad", "x", (), {}, valid_handler), "lowercase"),
        (lambda: Command("_hidden", "x", (), {}, valid_handler), "snake_case"),
        (
            lambda: Command(
                "run",
                "x",
                [ParameterDoc("x", str, False, ""), ParameterDoc("x", str, False, "")],
                {},
                valid_handler,
            ),
            "duplicate",
        ),
        (
            lambda: Command(
                "run",
                "x",
                [ParameterDoc(RUNTIME_DRYRUN_KEY, str, False, "")],
                {},
                valid_handler,
            ),
            "reserved",
        ),
        (lambda: InvalidCommand("run", "x", [object()], {}, valid_handler), "ParameterDoc"),
        (lambda: Command("run", "x", (), {"bad-key": 1}, valid_handler), "identifier"),
        (lambda: Command("run", "x", (), {"logger": 1}, valid_handler), "reserved"),
        (lambda: CommandGroup("Bad", "x", ()), "lowercase"),
        (lambda: CommandGroup("_hidden", "x", ()), "snake_case"),
        (lambda: InvalidCommandGroup("root", "x", [object()]), "commands or groups"),
    ],
)
def test_declarations_reject_invalid_names_and_children(factory: object, message: str) -> None:
    """Declaration validation covers collisions, reserved names, and child types."""
    with pytest.raises((TypeError, ValueError), match=message):
        factory()  # type: ignore[operator]


def test_handler_shape_and_docstring_boundaries_are_strict() -> None:
    """Wrong async shape fails and rST fields do not leak into summaries."""

    async def wrong_name(value: CliContext) -> CliResult:
        """Return a result.

        :param value: Current invocation.
        :returns: Successful result.
        """
        return CliResult(CliResultStatus.SUCCESS, "")

    async def wrong_return(context: CliContext) -> int:
        """Return a wrong result.

        :param context: Current invocation.
        :returns: Wrong result.
        """
        return 0

    with pytest.raises(TypeError, match="exactly context"):
        cli.command()(wrong_name)
    with pytest.raises(TypeError, match="annotations"):
        cli.command()(wrong_return)  # type: ignore[arg-type]
    command = cli.command()(valid_handler)
    assert command.summary == "Return a reusable valid result."

    async def unresolved(context: CliContext) -> CliResult:
        """Return a result with annotations changed below.

        :param context: Current invocation.
        :returns: Successful result.
        """
        return CliResult(CliResultStatus.SUCCESS, "")

    unresolved.__annotations__["return"] = "MissingCliResult"
    with pytest.raises(TypeError, match="cannot be resolved"):
        cli.command()(unresolved)

    unresolved.__doc__ = None
    unresolved.__annotations__["return"] = CliResult
    assert cli.command()(unresolved).summary == ""
