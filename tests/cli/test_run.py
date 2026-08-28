"""End-to-end behavioural tests for CLI execution."""

import asyncio
import json
import re
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.cli import (
    CliConfig,
    CliContext,
    CliEntrance,
    CliResult,
    CliResultStatus,
    Command,
    CommandGroup,
    LogConfig,
    ParameterDoc,
    cli,
)
from lclang.cli.logging import LoggerHandle
from lclang.cli.routing import RouteAction, RouteResult
from lclang.cli.run import execute_command, script_label_from_args, write_result

# Static configuration fixture used by the complete invocation case.
STATIC_CONFIG = "using \"child.lclcfg\"\nmessage: prefix + suffix\n"
# Static included configuration fixture used by the complete invocation case.
STATIC_CHILD = 'prefix: "hello "\nsuffix: "config"\ntoken!: "config-secret"\n'


def test_complete_run_uses_layers_context_logging_and_cleanup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A nested command observes static config, lazy overrides, date, and dryrun."""
    observed: dict[str, object] = {}

    @cli.command(
        parameter_docs=[
            ParameterDoc("message", str, True, "Rendered message"),
            ParameterDoc("token", str, True, "Private audit token", masked=True),
        ],
        preset={"preset_value": 2},
    )
    async def show_command(context: CliContext) -> CliResult:
        """Show the configured message.

        :param context: Current invocation.
        :returns: Successful rendered result.
        """
        observed["date"] = context.as_of_date
        observed["dryrun"] = context.dryrun
        observed["message"] = await context.frame.get("message")
        context.logger.info("message=%s", observed["message"])
        return CliResult(CliResultStatus.SUCCESS, str(observed["message"]))

    with TemporaryDirectory() as directory:
        root = Path(directory)
        config_path = root / "root.lclcfg"
        child_path = root / "child.lclcfg"
        config_path.write_text(STATIC_CONFIG, encoding="utf-8")
        child_path.write_text(STATIC_CHILD, encoding="utf-8")
        entrance = CliEntrance(
            CommandGroup("root", "Example", [show_command]),
            "1.2.3",
            CliConfig(LogConfig(log_dir=str(root / "logs"))),
        )
        status = asyncio.run(
            entrance.run(
                [
                    "python",
                    "tool.py",
                    "show",
                    "-c",
                    str(config_path),
                    "-o",
                    "message",
                    'LCL[prefix + "override"]',
                    "-o",
                    "token",
                    "override-secret",
                    "-a",
                    "20260809",
                    "-wif",
                ]
            )
        )
        assert status == 0
        assert capsys.readouterr().out == "hello override\n"
        assert observed == {"date": date(2026, 8, 9), "dryrun": True, "message": "hello override"}
        log_text = (root / "logs" / "lclang.log").read_text(encoding="utf-8")
        lines = log_text.splitlines()
        assert all(
            re.match(
                r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \| INFO +\| "
                r"lclang\.cli\.\d+ \| \w+\.py:\d+ \| \w+ \| .+ \| args=.*$",
                line,
            )
            for line in lines
        )
        messages = [line.split(" | ", 5)[5].rsplit(" | args=", 1)[0] for line in lines]
        assert messages[0] == 'execution.started command=["show"]'
        assert messages[1] == f"execution.log_file path={root / 'logs' / 'lclang.log'}"
        command_line = json.loads(messages[2].removeprefix("execution.command_line argv="))
        assert command_line == [
            "python",
            "tool.py",
            "show",
            "--config",
            str(config_path),
            "--override",
            "message",
            'LCL[prefix + "override"]',
            "--override",
            "token",
            "*masked*",
            "--as-of",
            "20260809",
            "--dryrun",
        ]
        execution_config = json.loads(
            messages[3].removeprefix("execution.config values=")
        )
        assert execution_config == {
            "as_of_date": "2026-08-09",
            "config_file_path": str(config_path),
            "dryrun": True,
            "overrides": {
                "message": 'LCL[prefix + "override"]',
                "token": "*masked*",
            },
            "verbose": False,
        }
        assert "message=hello override" in log_text
        assert "override-secret" not in "\n".join(messages[:4])


def test_help_and_version_short_circuit_execution(capsys: pytest.CaptureFixture[str]) -> None:
    """Built-ins render without calling a command or creating configuration state."""
    called = False

    @cli.command()
    async def work_command(context: CliContext) -> CliResult:
        """Perform work.

        :param context: Current invocation.
        :returns: Successful result.
        """
        nonlocal called
        called = True
        return CliResult(CliResultStatus.SUCCESS, "worked")

    entrance = CliEntrance(CommandGroup("root", "Example", [work_command]), "2.0.0")
    assert asyncio.run(entrance.run(["python", "tool.py", "-v"])) == 0
    assert asyncio.run(entrance.run(["python", "tool.py", "work", "--help"])) == 0
    assert called is False
    output = capsys.readouterr().out
    assert "tool.py 2.0.0" in output
    assert "Usage: tool.py work" in output


def make_result_entrance(status: CliResultStatus, description: str) -> CliEntrance:
    """Return an entrance whose handler emits one selected result.

    :param status: Handler result status.
    :param description: Handler result text.
    :returns: Reusable single-command entrance.
    """

    @cli.command(name="result")
    async def result_handler(context: CliContext) -> CliResult:
        """Return the selected result.

        :param context: Current invocation.
        :returns: Captured result value.
        """
        del context
        return CliResult(status, description)

    return CliEntrance(CommandGroup("root", "Results", [result_handler]))


@pytest.mark.parametrize(
    "status, description, expected_out, expected_err",
    [
        (CliResultStatus.SUCCESS, "ok", "ok\n", ""),
        (CliResultStatus.FAILURE, "failed", "", "failed\n"),
        (CliResultStatus.EXCEPTION, "exception", "", "exception\n"),
        (CliResultStatus.SUCCESS, "", "", ""),
    ],
)
def test_result_statuses_map_to_output_and_exit(
    status: CliResultStatus,
    description: str,
    expected_out: str,
    expected_err: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each explicit result status has deterministic output and integer mapping."""
    entrance = make_result_entrance(status, description)
    assert asyncio.run(entrance.run(["python", "tool.py", "result"])) == int(status)
    captured = capsys.readouterr()
    assert captured.out == expected_out
    assert captured.err == expected_err


def test_handler_exception_wrong_result_and_setup_failures_return_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ordinary handler and framework failures never escape the async boundary."""

    @cli.command(name="boom")
    async def boom_handler(context: CliContext) -> CliResult:
        """Raise an ordinary handler failure.

        :param context: Current invocation.
        :returns: No result because execution fails.
        :raises RuntimeError: Always.
        """
        del context
        raise RuntimeError("boom")

    @cli.command(name="wrong")
    async def wrong_handler(context: CliContext) -> CliResult:
        """Return an invalid runtime value.

        :param context: Current invocation.
        :returns: Deliberately invalid value at runtime.
        """
        del context
        return 1  # type: ignore[return-value]

    @cli.command(
        name="required",
        parameter_docs=[ParameterDoc("needed", str, True, "needed")],
    )
    async def required_handler(context: CliContext) -> CliResult:
        """Return an unreachable result.

        :param context: Current invocation.
        :returns: Unreachable result.
        """
        del context
        return CliResult(CliResultStatus.SUCCESS, "")

    entrance = CliEntrance(
        CommandGroup("root", "Failures", [boom_handler, wrong_handler, required_handler])
    )
    assert asyncio.run(entrance.run(["python", "tool.py", "boom"])) == 2
    assert asyncio.run(entrance.run(["python", "tool.py", "wrong"])) == 2
    assert asyncio.run(entrance.run(["python", "tool.py", "required"])) == 2
    assert asyncio.run(
        entrance.run(["python", "tool.py", "boom", "-c", "missing.lclcfg"])
    ) == 2
    errors = capsys.readouterr().err
    assert "boom" in errors
    assert "must return CliResult" in errors
    assert "missing required parameter" in errors
    assert "cannot load config" in errors


def test_routing_usage_and_direct_command_paths(capsys: pytest.CaptureFixture[str]) -> None:
    """Missing routes, scoped help, invalid version, and direct runs are mapped."""
    entrance = make_result_entrance(CliResultStatus.SUCCESS, "direct")
    command = entrance.command_group.commands[0]
    assert isinstance(command, Command)
    assert asyncio.run(entrance.run(["python", "tool.py"])) == 2
    assert asyncio.run(entrance.run(["python", "tool.py", "unknown"])) == 2
    assert asyncio.run(entrance.run(["python", "tool.py", "-v", "extra"])) == 2
    assert asyncio.run(entrance.run(["python", "tool.py", "-h"])) == 0
    assert asyncio.run(command.run(["python", "tool.py", "result"])) == 0
    assert asyncio.run(command.run(["python", "tool.py", "--help"])) == 0
    assert asyncio.run(command.run(["python", "tool", "result"])) == 2
    captured = capsys.readouterr()
    assert "direct" in captured.out
    assert "missing command" in captured.err
    assert "unknown command" in captured.err
    assert ".py" in captured.err


def test_low_level_result_writer_and_internal_params_guard(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Result logging can be suppressed and internal type mismatch is converted."""
    logger = __import__("logging").Logger("writer")
    handler = __import__("logging").NullHandler()
    logger.addHandler(handler)
    handle = LoggerHandle(logger, (handler,))
    with caplog.at_level(__import__("logging").INFO):
        write_result(CliResult(CliResultStatus.SUCCESS, "quiet"), handle, log_result=False)
    assert caplog.records == []
    write_result(CliResult(CliResultStatus.FAILURE, "low"), handle, log_result=False)
    command = make_result_entrance(CliResultStatus.SUCCESS, "").command_group.commands[0]
    assert isinstance(command, Command)
    assert asyncio.run(execute_command(command, object(), CliConfig())) == 2
    handle.close()
    captured = capsys.readouterr()
    assert captured.out == "quiet\n"
    errors = captured.err
    assert "low" in errors
    assert "params type mismatch" in errors
    assert script_label_from_args(["python", "folder/tool.py"]) == "tool.py"
    assert script_label_from_args(["python", r"folder\tool.py"]) == "tool.py"
    assert script_label_from_args(None) == "script.py"


def test_logger_cleanup_output_and_internal_route_failures_are_converted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Late framework failures are logged, cleaned, and returned as status two."""
    entrance = make_result_entrance(CliResultStatus.SUCCESS, "ok")
    assert asyncio.run(
        entrance.run(
            [
                "python",
                "tool.py",
                "result",
                "-o",
                "log_format",
                "bad",
            ]
        )
    ) == 2

    async def fail_close(self: object) -> None:
        """Raise one synthetic cleanup failure.

        :param self: Patched Frame stack.
        :returns: ``None``.
        :raises RuntimeError: Always.
        """
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr("lclang.cli.binding.FrameStack.close", fail_close)
    assert asyncio.run(entrance.run(["python", "tool.py", "result"])) == 2
    monkeypatch.undo()

    def fail_output(*args: object, **kwargs: object) -> None:
        """Raise one synthetic output failure.

        :param args: Ignored positional call values.
        :param kwargs: Ignored keyword call values.
        :returns: ``None``.
        :raises OSError: Always.
        """
        raise OSError("output failed")

    monkeypatch.setattr("lclang.cli.run.write_result", fail_output)
    assert asyncio.run(entrance.run(["python", "tool.py", "result"])) == 2
    monkeypatch.undo()

    def empty_route(root: object, tokens: object) -> RouteResult:
        """Return an internally invalid command route.

        :param root: Root group retained in the result.
        :param tokens: Ignored argv tokens.
        :returns: Command action without a command.
        """
        del tokens
        return RouteResult(RouteAction.COMMAND, root, None, (), ())  # type: ignore[arg-type]

    monkeypatch.setattr("lclang.cli.run.route_command", empty_route)
    assert asyncio.run(entrance.run(["python", "tool.py", "result"])) == 2
    monkeypatch.undo()
    assert asyncio.run(entrance.run(["python", "tool", "result"])) == 2
    errors = capsys.readouterr().err
    assert "log format" in errors
    assert "cleanup failed" in errors
    assert "route did not select" in errors
    assert ".py" in errors


def test_process_control_exception_propagates_after_cleanup() -> None:
    """KeyboardInterrupt is not converted into an ordinary CLI result."""

    @cli.command(name="interrupt")
    async def interrupt_handler(context: CliContext) -> CliResult:
        """Raise a process-control exception.

        :param context: Current invocation.
        :returns: No result because execution is interrupted.
        :raises KeyboardInterrupt: Always.
        """
        del context
        raise KeyboardInterrupt

    entrance = CliEntrance(CommandGroup("root", "Interrupt", [interrupt_handler]))
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(entrance.run(["python", "tool.py", "interrupt"]))
