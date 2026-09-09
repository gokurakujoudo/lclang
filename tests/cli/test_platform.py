"""Windows/POSIX token and subprocess integration tests for the CLI."""

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.cli.parser import parse_cli_params, split_argv
from tests.cli.platform_support import materialize_platform_case


def test_foreign_path_separators_and_opaque_tokens_are_host_neutral() -> None:
    """Windows and POSIX spellings retain exact executable and value tokens."""
    cases = (
        (r"C:\Python 3.14\python.exe", r"C:\tools 应用\sample.py"),
        ("/opt/Python 3.14/python", "/tmp/tools 应用/sample.py"),
    )
    for executable, script in cases:
        parts = split_argv(
            [
                executable,
                script,
                "admin",
                "show",
                "-c",
                "--config-looking.lclcfg",
                "-o",
                "literal",
                "--value-looking",
                "-o",
                "quoted",
                '"kept quotes"',
            ]
        )
        params = parse_cli_params(parts, ("admin", "show"), parts.tokens[2:])
        assert parts.script_label == "sample.py"
        assert params.executable_path == executable
        assert params.config_file_path == "--config-looking.lclcfg"
        assert params.overrides == {
            "literal": "--value-looking",
            "quoted": '"kept quotes"',
        }


def test_unicode_spaced_script_runs_without_a_shell_and_cleans_logs() -> None:
    """A static include graph, lazy override, dryrun, and log run in a subprocess."""
    temporary_path: Path
    with TemporaryDirectory() as directory:
        root = Path(directory)
        temporary_path = root
        script, config = materialize_platform_case(root)
        log_dir = root / "automatic logs"
        environment = os.environ.copy()
        source_root = Path(__file__).resolve().parents[2] / "src"
        environment["PYTHONPATH"] = str(source_root)
        environment["PYTHONIOENCODING"] = "utf-8"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "admin",
                "show",
                "-c",
                str(config),
                "-o",
                "message",
                'LCL[prefix + "✓"]',
                "-o",
                "literal",
                "--looks-like-option",
                "-o",
                "quoted",
                '"kept quotes"',
                "-o",
                "logger.file.app.directory",
                str(log_dir),
                "-a",
                "20260809",
                "-wif",
            ],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert completed.returncode == 0, completed.stderr
        log_path = next(log_dir.glob("*.log"))
        log_text = log_path.read_text(encoding="utf-8")
        assert completed.stdout.splitlines() == [
            'café ✓|--looks-like-option|"kept quotes"|2026-08-09|true'
        ]
        assert "message=café ✓" in completed.stderr
        assert "show_command" in completed.stderr
        assert "message=café ✓" in log_text
    assert temporary_path.exists() is False
