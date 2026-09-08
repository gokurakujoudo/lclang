"""Public API acceptance tests for the CLI subpackage."""

import lclang
import lclang.cli as cli_api


def test_cli_exports_are_curated_without_expanding_package_root() -> None:
    """CLI callers use one complete subpackage while root workflow stays focused."""
    expected = {
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
    }
    assert set(cli_api.__all__) == expected
    assert all(hasattr(cli_api, name) for name in expected)
    assert cli_api.RUNTIME_AS_OF_DATE_KEY == "__as_of_date__"
    assert cli_api.RUNTIME_CLI_PARAMS_KEY == "__cli_params__"
    assert cli_api.RUNTIME_DRYRUN_KEY == "__dryrun__"
    assert cli_api.RUNTIME_VERBOSE_KEY == "__verbose__"
    assert "CliEntrance" not in lclang.__all__
