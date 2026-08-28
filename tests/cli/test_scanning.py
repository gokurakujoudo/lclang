"""Recursive CLI command scanning contracts."""

from types import ModuleType

import pytest

from lclang.cli import CliContext, CliResult, cli, scan_commands
from tests.cli import scan_fixture


class CommandModule(ModuleType):
    """Module fixture accepting two explicitly typed command attributes."""

    first: object
    second: object


def test_scan_commands_imports_submodules_and_deduplicates_reexports() -> None:
    """A package tree becomes one deterministic flat command group."""
    group = scan_commands(scan_fixture, "root", "Scanned commands")
    assert [command.name for command in group.commands] == ["alpha", "beta"]


def test_scan_commands_rejects_distinct_duplicate_names() -> None:
    """Two different command objects cannot claim one scanned name."""
    module = CommandModule("duplicate_commands")

    @cli.command(name="same")
    async def first(context: CliContext) -> CliResult:
        """Return the first result.

        :param context: Current invocation.
        :returns: Successful empty result.
        """
        del context
        return CliResult.success("")

    @cli.command(name="same")
    async def second(context: CliContext) -> CliResult:
        """Return the second result.

        :param context: Current invocation.
        :returns: Successful empty result.
        """
        del context
        return CliResult.success("")

    module.first = first
    module.second = second
    with pytest.raises(ValueError, match="duplicate scanned command"):
        scan_commands(module, "root", "Duplicates")


def test_scan_commands_rejects_non_module_roots() -> None:
    """Discovery never treats arbitrary objects as import namespaces."""
    with pytest.raises(TypeError, match="root"):
        scan_commands(object(), "root", "Invalid")  # type: ignore[arg-type]
