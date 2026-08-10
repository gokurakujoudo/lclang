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
        "LogConfig",
        "ParameterDoc",
        "cli",
    }
    assert set(cli_api.__all__) == expected
    assert all(hasattr(cli_api, name) for name in expected)
    assert "CliEntrance" not in lclang.__all__
