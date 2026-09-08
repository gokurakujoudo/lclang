"""Public Frame configuration resolution without a CLI invocation."""

import logging
from io import StringIO

import pytest

from lclang import define_frame, define_module
from lclang.logger import (
    ConsoleConfig,
    FileConfig,
    Logger,
    LoggerHandlerConfig,
    LoggerRuntime,
    RotationConfig,
    RuntimeMetrics,
    SinkMetrics,
    resolve_logger_config,
    use_logger,
    use_logger_handler,
)
from lclang.logger.frame_config import logger_source, verbose_config
from lclang.runtime import Frame


@pytest.mark.asyncio
@pytest.mark.parametrize("verbose", [False, True])
async def test_absent_namespace_uses_handler_defaults(verbose: bool) -> None:
    """Unrelated definitions stay lazy while missing logging uses normal defaults."""
    async with define_frame(define_module("application", {"unused": "1 / 0"})) as frame:
        config = await resolve_logger_config(frame, verbose)
        assert isinstance(config, LoggerHandlerConfig)
        assert config.level == logging.NOTSET
        assert config.resolved_console().level == (logging.DEBUG if verbose else logging.INFO)
        assert config.resolved_files() == {}
        assert await frame.get("logger", fallback="absent") == "absent"


@pytest.mark.asyncio
async def test_public_types_and_layered_configuration() -> None:
    """Host overrides, inherited policies and scope results use public types."""
    stream = StringIO()
    module = define_module(
        "application",
        {
            "logger.console.level": '"WARNING"',
            "logger.file.default.enabled": "False",
            "logger.file.audit.filename": 'f"{service}.log"',
            "logger.file.audit.rotation.mode": '"time"',
            "logger.file.audit.rotation.interval": '"1h"',
            "unused": "1 / 0",
        },
    )
    async with (
        define_frame(module, preset={"service": "catalog"}) as parent,
        parent.derive(
            define_module("overrides", {}),
            values={"logger.console.level": "INFO", "logger.console.stream": stream},
        ) as frame,
    ):
        config = await resolve_logger_config(frame)
        console: ConsoleConfig = config.resolved_console()
        sink: FileConfig = config.resolved_files()["audit"]
        rotation: RotationConfig = sink.rotation
        assert isinstance(console, ConsoleConfig) and console.level == logging.INFO
        assert isinstance(sink, FileConfig) and not sink.enabled
        assert sink.filename == "catalog.log"
        assert isinstance(rotation, RotationConfig) and rotation.seconds == 3600
    async with use_logger_handler(config) as runtime:
        assert isinstance(runtime, LoggerRuntime)
        logger: Logger = await use_logger("application")
        assert isinstance(logger, Logger)
        logger.info("ready")
    metrics: RuntimeMetrics = runtime.metrics
    assert isinstance(metrics, RuntimeMetrics) and metrics.records_written == 1
    assert isinstance(metrics.sinks["console"], SinkMetrics)
    assert "ready" in stream.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["None", "{}", "1 / 0"])
async def test_present_namespace_is_never_treated_as_absent(source: str) -> None:
    """Defaults do not hide malformed or failing logger definitions."""
    from lclang.errors import LclEvaluationError

    async with define_frame(define_module("bad", {"logger": source})) as frame:
        with pytest.raises((TypeError, LclEvaluationError)):
            await resolve_logger_config(frame)


@pytest.mark.asyncio
async def test_invalid_logger_namespace_and_expression_report_paths() -> None:
    """Scalar replacement and failing configuration expressions fail before entry."""
    async with define_frame(define_module("bad", {"logger": "1"})) as frame:
        with pytest.raises(TypeError, match="FrameProxy"):
            await resolve_logger_config(frame)
    async with define_frame(define_module("bad", {"logger.console.level": "1 / 0"})) as frame:
        with pytest.raises(ValueError, match="logger.console.level"):
            await resolve_logger_config(frame)


def test_verbose_preserves_disabled_console_level() -> None:
    """Disabled sinks keep their original policy under a verbose invocation."""
    config = LoggerHandlerConfig(console={"enabled": False, "level": "ERROR"})
    assert verbose_config(config).resolved_console().level == logging.ERROR


@pytest.mark.asyncio
async def test_invalid_fields_include_defining_source() -> None:
    """Validation attaches source information without evaluating unrelated bindings."""
    async with define_frame(define_module("bad_settings", {"logger.level": '"NOPE"'})) as frame:
        with pytest.raises(ValueError, match="logger.level.*bad_settings"):
            await resolve_logger_config(frame)
    async with Frame(define_module("override_layer", {}), values={"logger.level": "NOPE"}) as frame:
        with pytest.raises(ValueError, match="logger.level.*override_layer"):
            await resolve_logger_config(frame)


@pytest.mark.asyncio
async def test_source_for_absent_and_inherited_fields() -> None:
    """Missing requirements name their layer; inherited failures point at the template."""
    async with define_frame(define_module("empty_layer", {})) as frame:
        assert logger_source(frame, "logger.level") == "empty_layer"
    async with define_frame(define_module("partial", {"logger.file.app.enabled": "True"})) as frame:
        with pytest.raises(ValueError, match="logger.file.app.directory.*partial"):
            await resolve_logger_config(frame)
    async with (
        define_frame(
            define_module("template", {"logger.file.default.rotation.align": "True"})
        ) as base,
        base.derive(
            define_module(
                "sink",
                {
                    "logger.file.app.enabled": "False",
                    "logger.file.app.rotation.interval": '"2h"',
                },
            )
        ) as frame,
    ):
        with pytest.raises(ValueError, match="logger.file.app.rotation.align.*template"):
            await resolve_logger_config(frame)
