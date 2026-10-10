"""CLI ownership survives iterator controls at handler, cleanup and output boundaries."""

import asyncio
import io
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

import pytest

from lclang.cli import CliConfig, CliContext, CliEntrance, CliParams, CliResult, CommandGroup, cli
from lclang.cli.builtin_command import parse_lcl_command
from lclang.error import LclError
from lclang.lang import Frame, define_frame, define_module
from lclang.logger import Logger, LoggerHandlerConfig

CONTROL_SOURCE = "__LCL_VERSION__: 1\nresource: make()\n"
STARTUP_SOURCE = "__LCL_VERSION__: 1\nlogger.console.stream: make_stream()\n"


@pytest.mark.parametrize("stage", ["handler", "group", "cleanup", "output"])
@pytest.mark.parametrize("group_entrance", [False, True])
def test_cli_preserves_protocol_identity_prior_failure_and_resource_state(
    stage: str, group_entrance: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Controls propagate after all owned resources close, retaining ordinary causes."""
    signal = StopAsyncIteration("done")
    original = (
        ExceptionGroup("protocol", [signal, OSError("member")]) if stage == "group" else signal
    )
    business = ValueError("business")
    cleanup = OSError("cleanup")
    frames: list[Frame] = []
    events: list[str] = []

    class Resource:
        async def aclose(self) -> None:
            events.append("close")
            if stage in {"handler", "group"}:
                raise cleanup
            if stage == "cleanup":
                raise signal

    @cli.command(preset={"make": Resource})
    async def control_command(context: CliContext) -> CliResult:
        frames.append(context.frame)
        assert isinstance(await context.frame.get("resource"), Resource)
        if stage in {"handler", "group"}:
            raise original
        raise business

    def fail_output(result: CliResult, logger: Logger, *, log_result: bool = True) -> None:
        raise signal

    if stage == "output":
        monkeypatch.setattr("lclang.cli.command_execution.write_result", fail_output)
    with TemporaryDirectory() as directory:
        path = Path(directory) / "controls.lclcfg"
        path.write_text(CONTROL_SOURCE, encoding="utf-8")
        entrance = CliEntrance(
            CommandGroup("root", "Root", [control_command]),
            cli_config=CliConfig(LoggerHandlerConfig(console={"enabled": False})),
        )
        with pytest.raises(Exception) as caught:
            runner = entrance.run if group_entrance else control_command.run
            asyncio.run(runner(["python", "tool.py", "control", "-c", str(path)]))
    assert caught.value is original
    assert events == ["close"] and frames[0].closed
    assert isinstance(original.__cause__, LclError)
    if stage in {"handler", "group"}:
        assert original.__cause__.__cause__ is cleanup
    else:
        assert original.__cause__.code == "LCL451811" and original.__cause__.__cause__ is business


def test_logger_startup_and_owned_stream_cleanup_are_reported_together(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A logger setup failure cannot hide invocation Frame cleanup failure."""
    streams: list[io.StringIO] = []
    original_start = Thread.start

    class Stream(io.StringIO):
        def close(self) -> None:
            super().close()
            raise OSError("owned stream close")

    def make_stream() -> io.StringIO:
        stream = Stream()
        streams.append(stream)
        return stream

    def fail_start(thread: Thread) -> None:
        if thread.name == "lclang.logger.writer":
            raise OSError("logger startup")
        original_start(thread)

    @cli.command(preset={"make_stream": make_stream})
    async def unused_command(context: CliContext) -> CliResult:
        raise AssertionError("body must not run")

    monkeypatch.setattr(Thread, "start", fail_start)
    with TemporaryDirectory() as directory:
        path = Path(directory) / "startup.lclcfg"
        path.write_text(STARTUP_SOURCE, encoding="utf-8")
        entrance = CliEntrance(CommandGroup("root", "Root", [unused_command]))
        assert asyncio.run(entrance.run(["python", "tool.py", "unused", "-c", str(path)])) == 2
    assert len(streams) == 1 and streams[0].closed
    output = capsys.readouterr().err
    assert "LCL625811" in output and "LCL236811" in output and "LCL451911" in output


@pytest.mark.asyncio
@pytest.mark.parametrize("grouped", [False, True])
async def test_evaluated_builtin_inspection_keeps_protocol_controls(grouped: bool) -> None:
    """The parse command displays ordinary cached failures and propagates controls."""
    signal = StopAsyncIteration("done")
    original = ExceptionGroup("protocol", [signal, OSError("member")]) if grouped else signal

    def fail() -> None:
        raise original

    async with define_frame(
        define_module("control", {"RESULT": "fail()"}), preset={"EVAL": True, "fail": fail}
    ) as frame:
        params = CliParams("python", ("parse_lcl",), date(2026, 1, 1), False, None, {})
        context = CliContext(
            params.as_of_date,
            False,
            frame,
            Logger("protocol-inspection", "", 0),
            params,
        )
        with pytest.raises(Exception) as caught:
            await parse_lcl_command.handler(context)
        assert caught.value is original
