"""Public typed framework for configuration-driven Python-script CLIs.

Exports ``CliConfig``, ``CliContext``, ``CliEntrance``, ``CliFacade``, ``CliParams``,
``CliResult``, ``CliResultStatus``, ``Command``, ``CommandGroup``, ``ParameterDoc``,
``RUNTIME_AS_OF_DATE_KEY``, ``RUNTIME_CLI_PARAMS_KEY``, ``RUNTIME_COMMAND_KEY``,
``RUNTIME_DRYRUN_KEY``, ``RUNTIME_EXECUTION_TIMESTAMP_KEY``, ``RUNTIME_VERBOSE_KEY``,
``RUNTIME_YMD_KEY``, ``cli``, ``scan_commands``.
"""

from lclang.cli.cli_models import (
    CliConfig,
    CliParams,
    CliResult,
    CliResultStatus,
    ParameterDoc,
)
from lclang.cli.command_definition import CliFacade, Command, CommandGroup, cli
from lclang.cli.command_discovery import scan_commands
from lclang.cli.command_entrance import CliEntrance
from lclang.cli.invocation_context import CliContext
from lclang.cli.invocation_key import (
    RUNTIME_AS_OF_DATE_KEY,
    RUNTIME_CLI_PARAMS_KEY,
    RUNTIME_COMMAND_KEY,
    RUNTIME_DRYRUN_KEY,
    RUNTIME_EXECUTION_TIMESTAMP_KEY,
    RUNTIME_VERBOSE_KEY,
    RUNTIME_YMD_KEY,
)

# Unitless public export names come from this module's supported API; the explicit list keeps
# implementation helpers out of wildcard imports.
__all__ = [
    "CliConfig",
    "CliContext",
    "CliEntrance",
    "CliFacade",
    "CliParams",
    "CliResult",
    "CliResultStatus",
    "Command",
    "CommandGroup",
    "ParameterDoc",
    "RUNTIME_AS_OF_DATE_KEY",
    "RUNTIME_CLI_PARAMS_KEY",
    "RUNTIME_COMMAND_KEY",
    "RUNTIME_DRYRUN_KEY",
    "RUNTIME_EXECUTION_TIMESTAMP_KEY",
    "RUNTIME_VERBOSE_KEY",
    "RUNTIME_YMD_KEY",
    "cli",
    "scan_commands",
]
