"""Behavioural tests for opt-in internal CLI tracing."""

import asyncio
import logging
from collections.abc import Generator
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.cli import (
    CliConfig,
    CliContext,
    CliEntrance,
    CliResult,
    CommandGroup,
    LogConfig,
    cli,
)
from lclang.cli.application import LCLANG_CLI_ENTRANCE


class BrokenRepresentation:
    """Provide a value whose representation is deliberately unusable."""

    def __repr__(self) -> str:
        """Raise instead of returning a representation.

        :returns: No representation.
        :raises RuntimeError: Always.
        """
        raise RuntimeError("representation failed")


class FailingAwaitable:
    """Provide a host value that fails during automatic awaiting."""

    def __await__(self) -> Generator[None, None, object]:
        """Raise when the evaluator requests the immediate value.

        :returns: Generator that never produces an immediate result.
        :raises RuntimeError: Always after empty iteration.
        """
        yield from ()
        raise RuntimeError("await failed")


def make_verbose_entrance(log_dir: str | None = None) -> CliEntrance:
    """Build a command exercising evaluated, cached, external, native, and fallback values.

    :param log_dir: Optional file-log directory.
    :returns: Reusable tracing entrance.
    """

    @cli.command(
        preset={
            "broken": BrokenRepresentation(),
            "failing_awaitable": FailingAwaitable(),
            "long_text": "line\n" + "x" * 240,
        }
    )
    async def trace_command(context: CliContext) -> CliResult:
        """Resolve representative values twice where caching applies.

        :param context: Current invocation.
        :returns: Successful evaluated result.
        """
        first, second = await asyncio.gather(
            context.frame.get("RESULT"),
            context.frame.get("RESULT"),
        )
        assert first == second
        result = first
        await context.frame.get("RESULT")
        await context.frame.get("len")
        await context.frame.get("missing", "fallback")
        await context.frame.get("broken")
        await context.frame.get("long_text")
        await context.frame.get("LOCAL_RESULT")
        with suppress(RuntimeError):
            await context.frame.get("failing_awaitable")
        with suppress(Exception):
            await context.frame.get("absent")
        return CliResult.success(str(result))

    config = CliConfig(LogConfig(log_dir=log_dir, log_level="ERROR"))
    return CliEntrance(CommandGroup("root", "Trace", [trace_command]), cli_config=config)


def trace_args(*extra: str) -> list[str]:
    """Return one complete lazy-expression invocation.

    :param extra: Options inserted before overrides.
    :returns: Full explicit argv.
    """
    return [
        "python",
        "tool.py",
        "trace",
        *extra,
        "-o",
        "external",
        "value",
        "-o",
        "RESULT",
        'LCL[external + "!"]',
        "-o",
        "LOCAL_RESULT",
        'LCL[((item) -> item)("local")]',
    ]


def test_verbose_is_silent_by_default_and_preserves_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ordinary invocations retain exact stdout with no internal diagnostics."""
    entrance = make_verbose_entrance()
    assert asyncio.run(entrance.run(trace_args())) == 0
    captured = capsys.readouterr()
    assert captured.out == "value!\n"
    assert captured.err == ""


def test_verbose_reports_parse_lookup_evaluation_and_safe_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verbose stderr identifies value provenance without trusting repr or line shape."""
    entrance = make_verbose_entrance()
    assert asyncio.run(entrance.run(trace_args("--verbose"))) == 0
    captured = capsys.readouterr()
    assert captured.out == "value!\n"
    trace = captured.err
    assert "[lclang.parse]" in trace
    assert "[lclang.evaluate]" in trace
    assert "source=external-provided value=(str) 'value'" in trace
    assert "source=lcl-evaluated value=(str) 'value!'" in trace
    assert "source=shared-lcl-evaluation value=(str) 'value!'" in trace
    assert "source=cached value=(str) 'value!'" in trace
    assert "source=native-provided" in trace
    assert "source=local-provided value=(str) 'local'" in trace
    assert "source=fallback value=(str) 'fallback'" in trace
    assert "value=(BrokenRepresentation) <repr failed: RuntimeError>" in trace
    assert "source=external-provided error=(RuntimeError)" in trace
    assert "source=missing" in trace
    assert "\\n" in trace
    assert "<truncated>" in trace


def test_verbose_replays_early_records_to_the_configured_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicit verbose mode reaches stderr and file despite an ERROR log level."""
    with TemporaryDirectory() as directory:
        entrance = make_verbose_entrance(directory)
        assert asyncio.run(entrance.run(trace_args("--verbose"))) == 0
        stderr = capsys.readouterr().err
        contents = (Path(directory) / "lclang.log").read_text(encoding="utf-8")
    assert "[lclang.parse]" in stderr
    assert "[lclang.parse]" in contents
    assert "source=fallback" in contents


def test_verbose_reports_evaluation_failures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Failed definitions retain both evaluation and lookup diagnostics."""
    @cli.command()
    async def failure_command(context: CliContext) -> CliResult:
        """Resolve the same failed definition twice to expose its cached failure.

        :param context: Current invocation.
        :returns: Successful result after retaining both failures.
        """
        with suppress(Exception):
            await context.frame.get("RESULT")
        with suppress(Exception):
            await context.frame.get("MISSING_RESULT")
        with suppress(Exception):
            await context.frame.get("RESULT")
        return CliResult.success("")

    entrance = CliEntrance(CommandGroup("root", "Failure", [failure_command]))
    args = [
        "python",
        "tool.py",
        "failure",
        "--verbose",
        "-o",
        "RESULT",
        "LCL[1 / 0]",
        "-o",
        "MISSING_RESULT",
        "LCL[missing_name]",
    ]
    assert asyncio.run(entrance.run(args)) == 0
    trace = capsys.readouterr().err
    assert "[lclang.evaluate]" in trace
    assert "source=lcl-evaluated error=(LclEvaluationError)" in trace
    assert "source=cached-failure error=(LclEvaluationError)" in trace
    assert "name='missing_name'" in trace and "source=missing" in trace
    assert "division by zero" in trace


def test_concurrent_invocations_keep_verbose_state_task_local(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A quiet sibling Task never emits its distinct values into verbose stderr."""
    entrance = make_verbose_entrance()
    root_handlers = tuple(logging.getLogger().handlers)

    async def exercise() -> tuple[int, int]:
        """Run one verbose and one ordinary invocation concurrently.

        :returns: Both process-compatible statuses.
        """
        noisy = trace_args("--verbose")
        quiet = trace_args()
        noisy[6] = "noisy-value"
        quiet[4] = "quiet_external"
        quiet[5] = "quiet-value"
        quiet[8] = 'LCL[quiet_external + "!"]'
        first, second = await asyncio.gather(entrance.run(noisy), entrance.run(quiet))
        return first, second

    assert asyncio.run(exercise()) == (0, 0)
    captured = capsys.readouterr()
    assert "noisy-value" in captured.err
    assert "quiet-value" not in captured.err
    assert tuple(logging.getLogger().handlers) == root_handlers


def test_builtin_cli_verbose_keeps_result_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The installed module entrance exposes the same leaf-command tracing."""
    args = [
        "python",
        "__main__.py",
        "eval_lcl",
        "--verbose",
        "-o",
        "RESULT",
        "LCL[40 + 2]",
    ]
    assert asyncio.run(LCLANG_CLI_ENTRANCE.run(args)) == 0
    captured = capsys.readouterr()
    assert captured.out == "42\n"
    assert "[lclang.parse]" in captured.err
    assert "source=lcl-evaluated value=(int) 42" in captured.err
