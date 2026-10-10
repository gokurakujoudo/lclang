"""Root command-group entrance declaration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from lclang.cli.commands import CommandGroup
from lclang.cli.models import CliConfig
from lclang.error import LclCliError
from lclang.error.base import LclValidationError
from lclang.error.boundary import guard_async_failure, guard_constructor, guard_failure
from lclang.error.codes.cli import Code as cli_codes
from lclang.runtime import Preset


@guard_constructor(LclValidationError, cli_codes.NATIVE_412)
@dataclass(frozen=True, slots=True)
class CliEntrance:
    """Bind one root command group to version and execution defaults.

    :param command_group: Descriptive root group not consumed from argv.
    :param version: Non-empty version text rendered by built-ins.
    :param cli_config: Immutable framework defaults.
    :param lcl_mixin: Shallow host defaults shared by every routed command.
    """

    command_group: CommandGroup
    version: str = "0.0.0"
    cli_config: CliConfig = field(default_factory=CliConfig)
    lcl_mixin: Mapping[str, object] = field(default_factory=dict[str, object], kw_only=True)

    @guard_failure(LclValidationError, cli_codes.NATIVE_412)
    def __post_init__(self) -> None:
        """Validate the entrance without touching process state.

        :returns: ``None``.
        :raises LclValidationError: If a field has the wrong public type.
        :raises LclValidationError: If version text or host binding names are invalid.
        """
        if not isinstance(self.command_group, CommandGroup):
            raise LclValidationError(
                "CLI entrance command group must be CommandGroup",
                code=cli_codes.E12_CLI_ENTRANCE_COMMAND_GROUP_MUST_BE_COMMANDGROUP,
            )
        if not isinstance(self.version, str):
            raise LclValidationError(
                "CLI entrance version must be text",
                code=cli_codes.E12_CLI_ENTRANCE_VERSION_MUST_BE_TEXT,
            )
        if not self.version:
            raise LclValidationError(
                "CLI entrance version cannot be empty",
                code=cli_codes.E12_CLI_ENTRANCE_VERSION_CANNOT_BE_EMPTY,
            )
        if not isinstance(self.cli_config, CliConfig):
            raise LclValidationError(
                "CLI entrance config must be CliConfig",
                code=cli_codes.E12_CLI_ENTRANCE_CONFIG_MUST_BE_CLICONFIG,
            )
        snapshot = dict(self.lcl_mixin)
        Preset("entrance", snapshot)
        object.__setattr__(self, "lcl_mixin", MappingProxyType(snapshot))

    @guard_async_failure(LclCliError, cli_codes.NATIVE_412)
    async def run(self, args: Sequence[str] | None = None) -> int:
        """Route and execute one full argv invocation.

        :param args: Full argv, or ``None`` to adapt current process argv.
        :returns: Integer program status.
        """
        from lclang.cli.run import run_entrance

        return await run_entrance(self, args)
