"""CLI failure reports appear once and preserve file traceback evidence."""

import asyncio
import re
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.cli import CliConfig, CliContext, CliEntrance, CliResult, CommandGroup, cli
from lclang.lang import Frame
from lclang.logger import LoggerHandlerConfig

# Static overrides exercise the real parser and Frame evaluation path.
FAILURE_ARGS = ["python", "tool.py", "fail", "--verbose", "-o", "RESULT", "LCL[1 / 0]"]


def test_exception_console_and_file_do_not_repeat_complete_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The final report is singular while native frames and the cause remain in files."""

    @cli.command(name="fail")
    async def fail(context: CliContext) -> CliResult:
        await context.frame.get("RESULT")
        return CliResult.success("unreachable")

    with TemporaryDirectory() as directory:
        entrance = CliEntrance(
            CommandGroup("root", "Errors", [fail]),
            cli_config=CliConfig(LoggerHandlerConfig(file={"app": {"directory": directory}})),
        )
        assert asyncio.run(entrance.run(FAILURE_ARGS)) == 2
        console = capsys.readouterr()
        content = next(Path(directory).glob("*.log")).read_text(encoding="utf-8")
    assert console.out == ""
    assert console.err.count("Error in evaluating RESULT") == 1
    assert console.err.count("Cause:") == 1
    assert "Python traceback:" not in console.err
    assert content.count("Error in evaluating RESULT") == 1
    assert "Python traceback:" in content and "Traceback (most recent call last):" in content
    assert "operator_evaluation.py" in content and "ZeroDivisionError: division by zero" in content
    match = re.search(r"Failed while evaluating RESULT.*\(failure (F\d+)\)", console.err)
    assert match is not None
    assert f"(failure {match.group(1)})" in content


@pytest.mark.parametrize("output_fails", [False, True])
def test_execution_cleanup_and_later_output_are_reported_without_repeating_members(
    output_fails: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Final cleanup groups retain members; a later output report references that group."""
    closed: list[Frame] = []
    original_close = Frame.close

    async def fail_close(frame: Frame) -> None:
        if frame.closed:
            return
        await original_close(frame)
        closed.append(frame)
        raise OSError("cleanup member")

    @cli.command(name="fail")
    async def fail(context: CliContext) -> CliResult:
        raise ValueError("business failed")

    def fail_output(*args: object, **kwargs: object) -> None:
        raise OSError("output channel failed")

    monkeypatch.setattr(Frame, "close", fail_close)
    if output_fails:
        monkeypatch.setattr("lclang.cli.command_execution.write_result", fail_output)
    with TemporaryDirectory() as directory:
        entrance = CliEntrance(
            CommandGroup("root", "Errors", [fail]),
            cli_config=CliConfig(LoggerHandlerConfig(file={"app": {"directory": directory}})),
        )
        assert asyncio.run(entrance.run(["python", "tool.py", "fail", "--verbose"])) == 2
        console = capsys.readouterr()
        content = next(Path(directory).glob("*.log")).read_text(encoding="utf-8")
    assert len(closed) == 3 and all(frame.closed for frame in closed)
    assert content.count("Cause: ValueError: business failed") == 1
    assert content.count("Cause: OSError: cleanup member") == 3
    assert content.count("Error in cleaning up command") == 1
    if output_fails:
        assert content.count("Error in writing command output") == 1
        assert "Earlier command failure: F" in content and "Members:" in content
        assert console.err.count("Error in writing command output") == 1
    else:
        assert console.err.count("Error in cleaning up command") == 1
        assert console.err.count("Cause: ValueError: business failed") == 1
        assert "Python traceback:" not in console.err


def test_output_failure_is_reported_to_stderr_without_verbose(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Failure in ordinary stdout output still has a readable stderr report."""

    @cli.command(name="success")
    async def success(context: CliContext) -> CliResult:
        return CliResult.success("result")

    def fail_output(*args: object, **kwargs: object) -> None:
        raise OSError("stdout unavailable")

    monkeypatch.setattr("lclang.cli.command_execution.write_result", fail_output)
    entrance = CliEntrance(CommandGroup("root", "Output", [success]))
    assert asyncio.run(entrance.run(["python", "tool.py", "success"])) == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err.count("Error in writing command output") == 1
    assert "stdout unavailable" in output.err


def test_cleanup_control_after_success_keeps_native_identity_and_no_failure_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A control raised during successful cleanup is never an ordinary CLI failure."""
    signal = StopAsyncIteration("cleanup control")
    requested: list[Frame] = []
    closed: list[Frame] = []
    original_close = Frame.close

    async def close_with_control(frame: Frame) -> None:
        if frame.closed:
            return
        await original_close(frame)
        closed.append(frame)
        if frame in requested:
            raise signal

    @cli.command(name="success")
    async def success(context: CliContext) -> CliResult:
        requested.append(context.frame)
        return CliResult.success("result")

    monkeypatch.setattr(Frame, "close", close_with_control)
    entrance = CliEntrance(CommandGroup("root", "Control", [success]))
    with pytest.raises(StopAsyncIteration) as caught:
        asyncio.run(entrance.run(["python", "tool.py", "success", "--verbose"]))
    assert caught.value is signal and len(closed) == 3 and all(frame.closed for frame in closed)
    output = capsys.readouterr()
    assert output.out == "" and "Reason:" not in output.err and "Cause:" not in output.err
