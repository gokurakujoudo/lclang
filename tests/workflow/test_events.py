"""Business events select and mask values before touching application objects."""

import asyncio
import inspect
import io
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import lclang
import lclang.workflow as wf
from lclang.logger import use_logger, use_logger_handler


@dataclass
class EventRecord:
    """Public and sensitive data in the same application record."""

    visible: str = "shown"
    secret: str = "hidden"


@pytest.mark.asyncio
async def test_business_event_fields_metadata_and_caller(caplog: pytest.LogCaptureFixture) -> None:
    """Explicit selections preserve branch, severity, dryrun, limits, and business location."""
    logger = logging.getLogger("workflow-events")
    async with lclang.define_frame() as frame:
        context = wf.TaskContext(
            True, date(2026, 9, 22), False, logger, frame,
            wf.define_task("root", "Root"), [wf.TaskID("root"), wf.TaskID("child")],
        )
        with caplog.at_level(logging.INFO, logger=logger.name):
            line = inspect.currentframe()
            assert line is not None
            expected = line.f_lineno + 1
            context.log_event("copied", record=EventRecord(), fields=("visible",), count=3)
            context.log_event("long", payload="x" * 300)
    event = caplog.records[0]
    assert event.lineno == expected and event.pathname == __file__
    assert event.__dict__["lclang_event"] == "copied"
    assert event.__dict__["lclang_task_branch"] == "root.child"
    assert event.__dict__["lclang_dryrun"] is True
    assert event.getMessage() == (
        "event 'copied': [root.child] (dryrun)\n    visible: 'shown'\n    count  : 3"
    )
    assert "hidden" not in event.getMessage() and "dryrun" in event.getMessage()
    assert "...<truncated>" in caplog.records[1].getMessage()


@pytest.mark.asyncio
async def test_disabled_and_masked_events_do_not_read_or_format(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Secrets are never fetched and disabled levels never inspect application payloads."""
    touches: list[str] = []

    class Value:
        def __repr__(self) -> str:
            touches.append("repr")
            raise AssertionError("must not render")

    @dataclass
    class Guarded:
        secret: object

        def __getattribute__(self, name: str) -> object:
            if name == "secret":
                touches.append("get")
                raise AssertionError("must not read")
            return object.__getattribute__(self, name)

    logger = logging.getLogger("workflow-guarded-events")
    async with lclang.define_frame(preset={"secret!": "same-object"}) as frame:
        context = wf.TaskContext(
            False, date(2026, 9, 22), False, logger, frame,
            wf.define_task("root", "Root"), [wf.TaskID("root")],
        )
        with caplog.at_level(logging.INFO, logger=logger.name):
            context.log_event("disabled", level=logging.DEBUG, record=Value(), value=Value())
            context.log_event(
                "masked", record=Guarded(Value()), fields=("secret",),
                masked_fields=("secret", "value"), value=Value(),
            )
            context.log_event("identity", value=await frame.get("secret"))
            context.log_event("empty")
        assert touches == []
        assert "\n    secret: *masked*\n    value : *masked*" in caplog.records[0].getMessage()
        assert "same-object" in caplog.records[1].getMessage()
        assert caplog.records[2].getMessage() == "event 'empty': [root]"


@pytest.mark.asyncio
async def test_event_selection_errors_are_explicit() -> None:
    """Only declared dataclass fields may be selected and each output name is unique."""
    logger = logging.getLogger("workflow-invalid-events")
    previous = logger.level
    logger.setLevel(logging.INFO)
    try:
        async with lclang.define_frame() as frame:
            context = wf.TaskContext(
                False, date(2026, 9, 22), False, logger, frame,
                wf.define_task("root", "Root"), [wf.TaskID("root")],
            )
            for record in ({"visible": "value"}, EventRecord):
                with pytest.raises(TypeError, match="dataclass instance"):
                    context.log_event("invalid", record=record)
            for selected in (("missing",), ("visible", "visible"), ("__repr__",)):
                with pytest.raises(ValueError, match="declared, unique"):
                    context.log_event("invalid", record=EventRecord(), fields=selected)
            with pytest.raises(ValueError):
                context.log_event("invalid", fields=("visible",))
            with pytest.raises(ValueError):
                context.log_event("invalid", record=EventRecord(), fields=("visible",), visible=2)
    finally:
        logger.setLevel(previous)


@pytest.mark.asyncio
async def test_lclang_logger_keeps_business_caller_and_configuration() -> None:
    """The existing logger queue receives one event with the application's source line."""
    stream = io.StringIO()
    async with use_logger_handler({
        "format": "%(filename)s:%(lineno)d %(levelname)s %(message)s",
        "console": {"stream": stream},
    }), lclang.define_frame() as frame:
        logger = await use_logger(prefix="[APP]")
        context = wf.TaskContext(
            False, date(2026, 9, 22), False, logger, frame,
            wf.define_task("root", "Root"), [wf.TaskID("root")],
        )
        line = inspect.currentframe()
        assert line is not None
        expected = line.f_lineno + 1
        context.log_event("warning", level=logging.WARNING, value=3)
    assert stream.getvalue().strip() == (
        f"test_events.py:{expected} WARNING [APP] event 'warning': [root]\n    value: 3"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("standard", [False, True])
async def test_multiline_events_reach_console_and_files(standard: bool) -> None:
    """Both logger entry points retain exactly the same complete message body."""
    stream = io.StringIO()
    with TemporaryDirectory() as directory:
        async with use_logger_handler({
            "format": "%(message)s", "console": {"stream": stream},
            "file": {"events": {"directory": directory}},
        }), lclang.define_frame() as frame:
            logger = logging.getLogger("multiline") if standard else await use_logger("multiline")
            context = wf.TaskContext(
                False, date(2026, 9, 23), False, logger, frame,
                wf.define_task("root", "Root"), [wf.TaskID("root")],
            )
            context.log_event("saved", first=1, longer=2)
        expected = "event 'saved': [root]\n    first : 1\n    longer: 2"
        assert stream.getvalue().count(expected) == 1
        files = await asyncio.to_thread(lambda: list(Path(directory).rglob("*.log")))
        assert files
        assert sum(path.read_text(encoding="utf-8").count(expected) for path in files) == 1


@pytest.mark.asyncio
async def test_disabled_event_does_not_consume_selection_iterators() -> None:
    """No iteration or validation occurs before a disabled severity is admitted."""
    def fail_iteration() -> list[str]:
        raise AssertionError("selection consumed")

    logger = logging.getLogger("disabled-selection")
    before = logger.level
    logger.setLevel(logging.ERROR)
    try:
        async with lclang.define_frame() as frame:
            context = wf.TaskContext(
                False, date(2026, 9, 23), False, logger, frame,
                wf.define_task("root", "Root"), [wf.TaskID("root")],
            )
            context.log_event(
                "ignored", fields=(name for _ in range(1) for name in fail_iteration()),
                masked_fields=(name for _ in range(1) for name in fail_iteration()),
            )
    finally:
        logger.setLevel(before)
