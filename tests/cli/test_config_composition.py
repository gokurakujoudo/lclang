"""Effective CLI overrides reach dependant expressions before evaluation starts."""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang.cli import CliConfig, CliContext, CliParams, CliResult, CliResultStatus, cli
from lclang.cli.binding import build_binding
from lclang.error import LclEvaluationError

CONFIG_SOURCES = {
    "derived": "base: 1\nresult: base + 1\n",
    "required": "base: NEED_OVERRIDE\nresult: base + 1\n",
    "runtime": "base: 7\nbase: RUNTIME_OVERRIDE\nresult: base + 1\n",
}


@cli.command(preset={"base": 20})
async def composition_command(context: CliContext) -> CliResult:
    """Return a derived configuration value.

    :param context: Effective CLI invocation.
    :returns: Successful result description.
    """
    return CliResult(CliResultStatus.SUCCESS, str(await context.frame.get("result")))


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["derived", "required", "runtime"])
async def test_lazy_cli_override_reaches_configuration_dependants(source: str) -> None:
    """Replacement ASTs affect dependencies, including required and runtime reservations."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "main.lclcfg"
        path.write_text(CONFIG_SOURCES[source], encoding="utf-8")
        params = CliParams(
            "python", ("composition",), date(2026, 10, 10), False, str(path), {"base": "LCL[10]"}
        )
        binding = await build_binding(composition_command, params, CliConfig())
        try:
            assert await binding.frame.get("result") == 11
            assert binding.frame.get_definition("base") is not None
        finally:
            await binding.stack.close()


@pytest.mark.asyncio
async def test_plain_cli_override_keeps_text_type_in_dependencies() -> None:
    """A plain argument remains host text and yields the native arithmetic failure."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "main.lclcfg"
        path.write_text(CONFIG_SOURCES["derived"], encoding="utf-8")
        params = CliParams(
            "python", ("composition",), date(2026, 10, 10), False, str(path), {"base": "10"}
        )
        binding = await build_binding(composition_command, params, CliConfig())
        try:
            with pytest.raises(LclEvaluationError) as failure:
                await binding.frame.get("result")
            assert isinstance(failure.value.__cause__, TypeError)
            assert "base = (str) '10'" in str(failure.value)
            assert binding.frame.get_definition("base") is None
        finally:
            await binding.stack.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["required", "runtime"])
async def test_host_preset_satisfies_only_runtime_reservation(source: str) -> None:
    """Low-priority Python values cannot supply a required configuration replacement."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "main.lclcfg"
        path.write_text(CONFIG_SOURCES[source], encoding="utf-8")
        params = CliParams("python", ("composition",), date(2026, 10, 10), False, str(path), {})
        binding = await build_binding(composition_command, params, CliConfig())
        try:
            if source == "required":
                with pytest.raises(LclEvaluationError, match="base needs a value"):
                    await binding.frame.get("result")
            else:
                assert await binding.frame.get("result") == 21
        finally:
            await binding.stack.close()
