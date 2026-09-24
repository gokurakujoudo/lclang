"""Inferred record metadata never creates a competing runtime schema."""

import logging
from dataclasses import InitVar, dataclass, field
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pytest

import lclang
from lclang.cli import CliConfig, CliParams, ParameterDoc
from lclang.cli.audit import redacted_overrides
from lclang.cli.binding import build_binding
from lclang.cli.help import render_command_help
from lclang.cli.parameter_details import DerivedParameterDoc
from lclang.utils import ValueBox, flatten_to_dict
from lclang.workflow import ExecutionStatus, TaskID, WorkflowExecutionContext, define_variable
from lclang.workflow.cli_parameters import expand_record_parameters
from lclang.workflow.mappings.records import can_construct_record
from tests.workflow.record_cli_support import CsvOptions, Dialect, make_workflow


def make_context(frame: lclang.Frame) -> WorkflowExecutionContext:
    """Use deterministic metadata and the caller-owned Frame."""
    return WorkflowExecutionContext(
        False,
        date(2026, 9, 23),
        False,
        logging.getLogger("csv"),
        frame,
    )


def test_inferred_help_and_default_factory_laziness() -> None:
    """Default metadata is display-only, including explicit None and factories."""
    variable = define_variable[CsvOptions]("csv", "CSV options")
    command = make_workflow(variable.quote).to_cli("convert", "Convert")
    docs = {item.name: item for item in command.parameter_docs}
    assert set(docs) == {
        "csv",
        "csv.encoding",
        "csv.dialect",
        "csv.dialect.delimiter",
        "csv.dialect.quote",
        "csv.headers",
        "csv.null",
    }
    text = render_command_help("tool", command, ("convert",))
    assert "Input encoding" in text and "Input separator" in text
    assert "default='utf-8'" in text and "default=None" in text and "default=<factory>" in text
    assert "NO HELP MESSAGE PROVIDED" in text
    assert not command.default_bindings
    assert all(item.default is None for item in docs.values())

    def fail_factory() -> str:
        raise AssertionError("help invoked a factory")

    @dataclass
    class Guarded:
        value: str = field(default_factory=fail_factory)

    inferred = expand_record_parameters((ParameterDoc("guarded", Guarded, False, "Guarded"),))
    assert isinstance(inferred[1], DerivedParameterDoc)
    assert inferred[1].help_default is not None
    assert inferred[1].help_default.factory is fail_factory


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [{}, {"csv.dialect.delimiter": ";"}])
async def test_cli_and_direct_execution_share_constructor_defaults(
    overrides: dict[str, str],
) -> None:
    """Absent records and partial nested scopes share the same constructor path."""
    workflow = make_workflow(define_variable[CsvOptions]("csv").quote)
    command = workflow.to_cli("convert", "Convert")
    params = CliParams("python", ("convert",), date(2026, 9, 23), False, None, overrides)
    binding = await build_binding(command, params, CliConfig())
    try:
        result = await workflow.execute(make_context(binding.frame))
        assert result.execution_status.status is ExecutionStatus.SUCCESS
        value = cast(CsvOptions, result.task_args[TaskID("convert")])
    finally:
        await binding.stack.close()
    async with lclang.define_frame(preset=dict(overrides)) as frame:
        direct = await workflow.execute(make_context(frame))
    other = cast(CsvOptions, direct.task_args[TaskID("convert")])
    expected = CsvOptions(dialect=Dialect(overrides.get("csv.dialect.delimiter", ",")))
    assert value == other == expected
    assert value.headers is not other.headers


@pytest.mark.asyncio
async def test_flattened_presets_and_unknown_override_paths() -> None:
    """Convenient field presets preserve configuration precedence and reject typos."""
    workflow = make_workflow(define_variable[CsvOptions]("csv").quote)
    preset = flatten_to_dict(CsvOptions(encoding="gbk"), "csv")
    # computed is an instance field, but not a configurable constructor input.
    preset.pop("csv.computed")
    command = workflow.to_cli("convert", "Convert", preset=preset)
    params = CliParams(
        "python",
        ("convert",),
        date(2026, 9, 23),
        False,
        None,
        {"csv.dialect.delimiter": ";"},
    )
    binding = await build_binding(command, params, CliConfig())
    try:
        result = await workflow.execute(make_context(binding.frame))
        actual = cast(CsvOptions, result.task_args[TaskID("convert")])
        assert actual.encoding == "gbk" and actual.dialect.delimiter == ";"
    finally:
        await binding.stack.close()
    assert await command.run(["python", "tool.py", "-o", "csv.delimter", ";"]) == 2
    with pytest.raises(ValueError, match="non-external"):
        workflow.to_cli("convert", "Convert", preset={"csv.typo": 1})


@pytest.mark.asyncio
async def test_entity_and_child_paths_remain_mutually_exclusive() -> None:
    """Field inference does not turn Frame bindings into a deep-merge engine."""
    command = make_workflow(define_variable[CsvOptions]("csv").quote).to_cli(
        "convert",
        "Convert",
        preset={"csv": CsvOptions()},
    )
    params = CliParams(
        "python",
        ("convert",),
        date(2026, 9, 23),
        False,
        None,
        {"csv.encoding": "ascii"},
    )
    with pytest.raises(ValueError):
        await build_binding(command, params, CliConfig())


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["declaration", "preset", "configuration"])
async def test_root_masks_cover_derived_help_and_override_audits(source: str) -> None:
    """Exact-name runtime masks expand only over the statically known record fields."""
    variable = define_variable[CsvOptions]("csv", is_masked=source == "declaration")
    command = make_workflow(variable.quote).to_cli(
        "convert",
        "Convert",
        preset={"csv!": CsvOptions()} if source == "preset" else None,
    )
    if source != "configuration":
        text = render_command_help("tool", command, ("convert",))
        assert "utf-8" not in text
    with TemporaryDirectory() as directory:
        path = Path(directory) / "config.lclcfg"
        path.write_text("csv!: FRAME_PROXY\ncsv.encoding: 'secret'\n", encoding="utf-8")
        params = CliParams(
            "python",
            ("convert",),
            date(2026, 9, 23),
            False,
            str(path) if source == "configuration" else None,
            {} if source == "preset" else {"csv.encoding": "secret"},
        )
        binding = await build_binding(command, params, CliConfig())
        try:
            assert binding.frame.is_masked("csv.encoding")
            assert "secret" not in str(redacted_overrides(params, binding.frame))
        finally:
            await binding.stack.close()


def test_generics_cycles_boxes_and_explicit_field_precedence() -> None:
    """Static expansion is finite and compatible explicit declarations retain their help."""

    @dataclass
    class Record[T]:
        value: T

    docs = expand_record_parameters((ParameterDoc("record", Record[int], True, "Record"),))
    assert docs[1].value_type is int and docs[1].required
    boxed = expand_record_parameters((ParameterDoc("box", ValueBox[str | None], True, "Box"),))
    assert len(boxed) == 1
    explicit = ParameterDoc("csv.encoding", str, False, "Explicit")
    combined = expand_record_parameters(
        (ParameterDoc("csv", CsvOptions, False, "CSV", masked=True), explicit)
    )
    chosen = next(item for item in combined if item.name == "csv.encoding")
    assert chosen.description == "Explicit" and chosen.masked
    with pytest.raises(TypeError, match="conflicting"):
        expand_record_parameters(
            (
                ParameterDoc("csv", CsvOptions, False, "CSV"),
                ParameterDoc("csv.encoding", int, False, "Wrong"),
            )
        )

    @dataclass
    class Cycle:
        child: object

    Cycle.__annotations__["child"] = Cycle
    recursive = expand_record_parameters((ParameterDoc("cycle", Cycle, True, "Cycle"),))
    assert [item.name for item in recursive] == ["cycle", "cycle.child"]

    @dataclass
    class InvalidHelp:
        value: str = field(default="", metadata={"help": 42})

    with pytest.raises(TypeError):
        expand_record_parameters((ParameterDoc("invalid", InvalidHelp, False, "Invalid"),))


def test_required_init_variables_are_not_mistaken_for_optional_records() -> None:
    """Constructor-only inputs remain required even though fields() omits them."""

    @dataclass
    class Record:
        required: InitVar[str]
        visible: str = "default"

    assert not can_construct_record(Record)
    docs = expand_record_parameters((ParameterDoc("record", Record, True, "Record"),))
    assert [item.name for item in docs] == ["record", "record.visible"]
