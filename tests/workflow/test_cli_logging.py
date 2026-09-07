"""Isolation contracts for optional workflow presentation."""

import asyncio
import logging
from unittest.mock import patch

import pytest

from lclang import define_frame
from lclang.workflow.cli_logging import log_lunch_option
from lclang.workflow.models import ExecutionStatus


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["masking", "read", "choice", "logger"])
async def test_lunch_ordinary_failures_never_escape(operation: str) -> None:
    """Every operation in the easter egg shares one ordinary-exception boundary."""
    async with define_frame(preset={"lunch.options": ["rice"]}) as frame:
        logger = logging.Logger("lunch-isolation")
        targets = {
            "masking": (frame, "is_masked"),
            "read": (frame, "get"),
            "logger": (logger, "info"),
        }
        if operation == "choice":
            with patch("lclang.workflow.cli_logging.random.choice", side_effect=RuntimeError):
                await log_lunch_option(logger, frame, ExecutionStatus.SUCCESS)
        else:
            owner, name = targets[operation]
            with patch.object(owner, name, side_effect=RuntimeError):
                await log_lunch_option(logger, frame, ExecutionStatus.SUCCESS)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
async def test_lunch_preserves_cancellation_and_process_control(
    error: type[BaseException],
) -> None:
    """Control-flow exceptions retain their existing propagation semantics."""
    async with define_frame(preset={"lunch.options": ["rice"]}) as frame:
        with patch.object(frame, "get", side_effect=error), pytest.raises(error):
            await log_lunch_option(logging.Logger("lunch-control"), frame, ExecutionStatus.SUCCESS)
