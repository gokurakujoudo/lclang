"""Behavioural tests for invocation context and entrance values."""

import logging
from datetime import date

import pytest

from lclang.cli import (
    CliConfig,
    CliContext,
    CliEntrance,
    CliParams,
    CliResult,
    CliResultStatus,
    CommandGroup,
    cli,
)
from lclang.runtime import Frame, Module
from lclang.types import ModuleName


@cli.command()
async def context_command(context: CliContext) -> CliResult:
    """Return a reusable context result.

    :param context: Current invocation.
    :returns: Successful result.
    """
    return CliResult(CliResultStatus.SUCCESS, "")


def context_values() -> tuple[date, Frame, logging.Logger, CliParams]:
    """Return valid values used by context validation cases.

    :returns: Date, Frame, Logger, and params tuple.
    """
    as_of = date(2026, 8, 9)
    frame = Frame(Module(ModuleName("context-test"), {}))
    logger = logging.Logger("context-test")
    params = CliParams("python", ("run",), as_of, False, None, {})
    return as_of, frame, logger, params


def test_context_and_entrance_validate_public_references() -> None:
    """Correct values are retained while each wrong public type is rejected."""
    as_of, frame, logger, params = context_values()
    context = CliContext(as_of, False, frame, logger, params)
    assert context.raw_params is params
    with pytest.raises(TypeError):
        CliContext("today", False, frame, logger, params)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CliContext(as_of, 1, frame, logger, params)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CliContext(as_of, False, object(), logger, params)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CliContext(as_of, False, frame, object(), params)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CliContext(as_of, False, frame, logger, object())  # type: ignore[arg-type]
    group = CommandGroup("root", "root", [context_command])
    assert CliEntrance(group).cli_config == CliConfig()
    with pytest.raises(TypeError):
        CliEntrance(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        CliEntrance(group, 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        CliEntrance(group, "")
    with pytest.raises(TypeError):
        CliEntrance(group, "1", object())  # type: ignore[arg-type]
