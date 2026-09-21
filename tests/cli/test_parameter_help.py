"""Scoped parameter help and static default presentation contracts."""

from collections.abc import Awaitable, Callable, Mapping

import pytest

from lclang.cli import CliContext, CliEntrance, CliResult, CommandGroup, ParameterDoc, cli
from lclang.cli.help import render_command_help


async def unused(context: CliContext) -> CliResult:
    """Fail if help accidentally executes the command."""
    raise AssertionError("help executed the handler")


def test_help_protects_default_representations() -> None:
    """A masked default is never rendered, while long defaults remain bounded."""
    class Unprintable:
        def __repr__(self) -> str:
            raise AssertionError("must not render masked value")

    command = cli.command(
        parameter_docs=[
            ParameterDoc("secret", object, True, "Secret", masked=True),
            ParameterDoc("long", str, True, "Long"),
        ], preset={"secret": Unprintable(), "long": "x" * 300},
    )(unused)
    rendered = render_command_help("tool.py", command, ("unused",))
    assert "default=*masked*" in rendered
    assert "repr failed" not in rendered
    assert "...<truncated>" in rendered
    assert max(map(len, rendered.splitlines())) <= 100


def test_scopes_annotations_defaults_and_masks() -> None:
    """Defaults respect runtime precedence and scopes retain copyable names."""
    command = cli.command(
        parameter_docs=[
            ParameterDoc("workflow.inbound_file.root", str, True, "Root"),
            ParameterDoc("csv.Zebra", Mapping[str, Callable[[str], Awaitable[str]]], True, "Map"),
            ParameterDoc("csv.alpha", str | None, True, "Escape"),
            ParameterDoc("plain", int, True, "Count", 3),
            ParameterDoc("workflow.token", str, True, "Token"),
        ],
        preset={"csv.alpha": None, "plain": 9, "workflow.token!": "secret"},
    )(unused)
    rendered = render_command_help("tool.py", command, ("unused",))
    assert "collections.abc." not in rendered
    assert "Mapping[str, Callable[[str], Awaitable[str]]]" in " ".join(rendered.split())
    assert rendered.index("(global):") < rendered.index("csv:")
    assert rendered.index("csv:") < rendered.index("workflow:")
    assert rendered.index("workflow:") < rendered.index("workflow.inbound_file:")
    assert rendered.index("csv.alpha") < rendered.index("csv.Zebra")
    assert "optional, default=None. Escape" in rendered
    assert "optional, default=3. Count" in rendered
    assert "optional, default=*masked*. Token" in rendered
    assert "secret" not in rendered
    assert "str; required. Root" in rendered


@pytest.mark.asyncio
async def test_entrance_help_merges_defaults_without_loading_config(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Help sees entrance defaults but does not load even an invalid config path."""
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("help loaded configuration")

    monkeypatch.setattr("lclang.cli.binding.load_config", forbidden)
    command = cli.command(
        parameter_docs=[
            ParameterDoc("value", int, True, "Value"),
            ParameterDoc("token", str, True, "Token"),
            ParameterDoc("empty", str | None, True, "Empty"),
        ], preset={"value": 2},
    )(unused)
    entrance = CliEntrance(
        CommandGroup("root", "Root", [command]),
        lcl_mixin={"value": 1, "token!": "secret", "empty": None, "helper": abs},
    )
    assert await entrance.run(["python", "tool.py", "unused", "-c", "missing", "--help"]) == 0
    rendered = capsys.readouterr().out
    assert "optional, default=2. Value" in rendered
    assert "optional, default=None. Empty" in rendered
    assert "optional, default=*masked*. Token" in rendered
    assert "helper" not in rendered
    assert "secret" not in rendered
    assert command.preset == {"value": 2}
    assert await command.run(["python", "tool.py", "--help"]) == 0
    assert "str; required. Token" in capsys.readouterr().out
