"""Root command-group entrance declaration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from lclang.cli.commands import CommandGroup
from lclang.cli.models import CliConfig


@dataclass(frozen=True, slots=True)
class CliEntrance:
    """Bind one root command group to version and execution defaults.

    :param command_group: Descriptive root group not consumed from argv.
    :param version: Non-empty version text rendered by built-ins.
    :param cli_config: Immutable framework defaults.
    """

    command_group: CommandGroup
    version: str = "0.0.0"
    cli_config: CliConfig = field(default_factory=CliConfig)

    def __post_init__(self) -> None:
        """Validate the entrance without touching process state.

        :returns: ``None``.
        :raises TypeError: If a field has the wrong public type.
        :raises ValueError: If version text is empty.
        """
        if not isinstance(self.command_group, CommandGroup):
            raise TypeError("CLI entrance command group must be CommandGroup")
        if not isinstance(self.version, str):
            raise TypeError("CLI entrance version must be text")
        if not self.version:
            raise ValueError("CLI entrance version cannot be empty")
        if not isinstance(self.cli_config, CliConfig):
            raise TypeError("CLI entrance config must be CliConfig")

    async def run(self, args: Sequence[str] | None = None) -> int:
        """Route and execute one full argv invocation.

        :param args: Full argv, or ``None`` to adapt current process argv.
        :returns: Integer program status.
        """
        from lclang.cli.run import run_entrance

        return await run_entrance(self, args)
