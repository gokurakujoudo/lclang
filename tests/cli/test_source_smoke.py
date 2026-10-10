"""Source integration contract for configuration, CLI logging and ownership."""

import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.cli import CliContext, CliEntrance, CliResult, CliResultStatus, CommandGroup, cli
from lclang.error import LclStateError
from lclang.lang.runtime import Frame
from lclang.logger.logger import Logger

# Fixed configuration fixtures exercise inclusion and derived overrides together.
SHARED_SOURCE = "base: 40\n"
OPTIONAL_SOURCE = 'local_value: "local"\n'
ENTRY_SOURCE = (
    'using "shared.lclcfg"\n'
    'using? "absent.lclcfg"\n'
    'using? "local.lclcfg"\n'
    "base: 41\nanswer: base + 1\n"
)


@pytest.mark.asyncio
async def test_source_cli_configuration_logging_and_cleanup() -> None:
    """A real source invocation evaluates overrides, writes logs and closes owners."""
    frames: list[Frame] = []
    loggers: list[logging.Logger | Logger] = []

    @cli.command()
    async def check_command(context: CliContext) -> CliResult:
        """Record the derived answer and retain owners for cleanup assertions."""
        frames.append(context.frame)
        loggers.append(context.logger)
        assert await context.frame.get("answer") == 43
        assert await context.frame.get("local_value") == "local"
        assert context.dryrun
        context.logger.info("source-answer=43")
        return CliResult(CliResultStatus.SUCCESS, "")

    application = CliEntrance(CommandGroup("root", "Source smoke", [check_command]))
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "shared.lclcfg").write_text(SHARED_SOURCE, encoding="utf-8")
        (root / "local.lclcfg").write_text(OPTIONAL_SOURCE, encoding="utf-8")
        entry = root / "entry.lclcfg"
        entry.write_text(ENTRY_SOURCE, encoding="utf-8")
        logs = root / "logs"
        assert (
            await application.run(
                [
                    sys.executable,
                    "smoke.py",
                    "check",
                    "-c",
                    str(entry),
                    "-o",
                    "answer",
                    "LCL[base + 2]",
                    "-wif",
                    "-o",
                    "logger.file.app.directory",
                    str(logs),
                ]
            )
            == 0
        )
        assert "source-answer=43" in next(logs.glob("*.log")).read_text(encoding="utf-8")
        assert frames and all(frame.closed for frame in frames)
        assert loggers
        for logger in loggers:
            assert isinstance(logger, Logger)
            with pytest.raises(LclStateError):
                logger.info("after close")
