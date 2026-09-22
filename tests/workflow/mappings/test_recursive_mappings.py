"""Recursive mapping behavior through the public workflow boundary."""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, assert_type, cast

import pytest

import lclang
import lclang.workflow as wf
from lclang.workflow.mappings import mapped_outputs, materialize_args


@dataclass
class Options:
    """Nested scalar and shared collection."""

    encoding: str
    shared: list[str]


@dataclass
class Arguments:
    """Grouped options."""

    options: Options


async def echo(
    context: wf.TaskContext, args: Arguments, status_mgr: wf.ExecutionStatusManager,
) -> Arguments:
    """Return the materialized grouped arguments."""
    return args


@pytest.mark.asyncio
async def test_nested_quotes_materialize_publish_and_infer() -> None:
    """A nested quote has the same meaning in execution and CLI discovery."""
    encoding = wf.define_variable[str]("csv.encoding")
    output = wf.define_variable[str]("result.encoding")
    shared: list[str] = []
    template = Arguments(Options(encoding.quote, shared))
    task = wf.define_task(
        "transform", "Transform", task_action=echo, args_mapping=template,
        outputs_mapping=Arguments(Options(output.quote, shared)),
    )
    workflow = wf.define_workflow("Nested", task)
    assert [item.name for item in workflow.to_cli("run", "Run").parameter_docs] == [
        "csv.encoding",
    ]
    async with lclang.define_frame(preset={"csv.encoding": "utf-8"}) as frame:
        result = await workflow.execute(wf.WorkflowExecutionContext(
            False, date(2026, 9, 22), True, logging.getLogger("nested"), frame,
        ))
        actual = result.task_args[wf.TaskID("transform")]
        assert isinstance(actual, Arguments)
        assert actual.options.encoding == "utf-8"
        assert actual.options.shared is shared
        assert template.options.encoding is encoding.quote
        assert await frame.get("result.encoding") == "utf-8"


@pytest.mark.asyncio
async def test_nested_projection_reads_concrete_record() -> None:
    """A field projection retains its producer as the external input."""
    source = wf.define_variable[Arguments]("source")
    projection = source.field("options", Options).field("encoding", str)
    task = wf.define_task(
        "project", "Project", task_action=echo,
        args_mapping=Arguments(Options(projection.quote, [])),
    )
    workflow = wf.define_workflow("Projection", task)
    assert [item.name for item in workflow.to_cli("run", "Run").parameter_docs] == ["source"]
    async with lclang.define_frame(preset={"source": Arguments(Options("utf-8", []))}) as frame:
        result = await workflow.execute(wf.WorkflowExecutionContext(
            False, date(2026, 9, 22), True, logging.getLogger("nested"), frame,
        ))
    assert result.task_outputs[wf.TaskID("project")] == Arguments(Options("utf-8", []))


@dataclass
class Generic[T]:
    """Generic record containing nested annotation forms."""

    value: T
    items: list[T]
    mapping: Mapping[str, T]
    convert: Callable[[T], T]
    optional: T | None = None


@dataclass
class Flexible:
    """An opaque field permitting cyclic input fixture construction."""

    value: Any


@dataclass
class Deferred:
    """An init-disabled field can be published but cannot receive input quotes."""

    value: int = field(init=False, default=2)


@pytest.mark.asyncio
async def test_nested_scope_records_and_generic_projection() -> None:
    """Workflow recursively materializes scope records without changing proxy APIs."""
    source = wf.define_variable[Arguments]("source")
    async with lclang.define_frame(preset={
        "source.options.encoding": "utf-8", "source.options.shared": [],
    }) as frame:
        actual = await materialize_args(source.quote, frame)
        assert actual == Arguments(Options("utf-8", []))
        proxy = cast(lclang.FrameProxy, await frame.get("source"))
        shallow = await proxy.as_record(Arguments)
        assert isinstance(shallow.options, lclang.FrameProxy)
    variable = wf.define_variable[Generic[int]]("generic")
    selected = variable.field("value", int)
    assert_type(selected.quote, int)
    value = Generic(7, [7], {"a": 7}, abs)
    async with lclang.define_frame(preset={"generic": value}) as frame:
        result = await materialize_args(Flexible(selected.quote), frame)
        assert result == Flexible(7)
        assert await materialize_args(variable.quote, frame) is value
    assert variable.field("items", list[int]).value_type == list[int]


@pytest.mark.asyncio
async def test_nested_whole_quote_and_shared_template_identity() -> None:
    """Concrete quoted resources retain identity and literal DAG templates resolve twice."""
    options = Options("utf-8", [])
    variable = wf.define_variable[Options]("options")
    async with lclang.define_frame(preset={"options": options}) as frame:
        result = cast(Arguments, await materialize_args(Arguments(variable.quote), frame))
        assert result.options is options
        template = Flexible([variable.quote])
        actual = cast(Flexible, await materialize_args(template, frame))
        assert actual.value is template.value
        assert await materialize_args(Deferred(), frame) == Deferred()
    @dataclass
    class Twice:
        first: Options
        second: Options
    twice_template = Twice(options, options)
    async with lclang.define_frame() as frame:
        actual_twice = cast(Twice, await materialize_args(twice_template, frame))
        assert actual_twice == twice_template
        assert actual_twice.first.shared is options.shared
        assert actual_twice.second.shared is options.shared


def test_invalid_templates_and_projection_contracts() -> None:
    """Definition validation rejects cycles and malformed reference contracts."""
    from lclang.workflow.mappings import require_mapping

    cyclic = Flexible(None)
    cyclic.value = cyclic
    with pytest.raises(ValueError, match="cyclic"):
        require_mapping(cyclic, "argument")
    wrong = wf.define_variable[int]("wrong")
    with pytest.raises(TypeError, match="options.encoding.*wrong"):
        require_mapping(Arguments(Options(cast(str, wrong.quote), [])), "argument")
    record = wf.define_variable[Options]("options")
    with pytest.raises(ValueError, match="unknown workflow field"):
        record.field("absent", str)
    with pytest.raises(TypeError, match="annotation mismatch"):
        record.field("encoding", int)
    with pytest.raises(TypeError, match="dataclass"):
        wrong.field("imag", int)
    projection = record.field("encoding", str)
    with pytest.raises(TypeError, match="read-only"):
        require_mapping(Options(projection.quote, []), "output")
    deferred = Deferred()
    deferred.value = wrong.quote
    with pytest.raises(TypeError, match="init field"):
        require_mapping(deferred, "argument")


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, 42])
async def test_projection_runtime_errors_retain_mapping_path(value: object) -> None:
    """Null and wrong Python values identify the failed reference and mapping."""
    source = wf.define_variable[Arguments]("source")
    projection = source.field("options", Options).field("encoding", str)
    async with lclang.define_frame(preset={"source": Arguments(cast(Options, value))}) as frame:
        with pytest.raises(TypeError, match="source.options.encoding") as caught:
            await materialize_args(Arguments(Options(projection.quote, [])), frame)
    assert any("options.encoding" in note for note in caught.value.__notes__)


@pytest.mark.asyncio
async def test_nested_output_failures_publish_nothing() -> None:
    """Extraction errors and destination name conflicts never publish a prefix."""
    one = wf.define_variable[str]("result.value")
    duplicate = wf.define_variable[list[str]]("result.value", is_masked=True)
    source = wf.define_variable[Options]("source")
    async with lclang.define_frame() as frame:
        with pytest.raises(ValueError, match="duplicate"):
            await mapped_outputs(
                Options(one.quote, duplicate.quote), Options("a", []), frame,
            )
        with pytest.raises(TypeError, match="read-only"):
            await mapped_outputs(Options(source.field("encoding", str).quote, []),
                                 Options("a", []), frame)
        with pytest.raises(TypeError, match="mapping dataclass"):
            await mapped_outputs(Arguments(Options(one.quote, [])),
                                 Arguments(cast(Options, 3)), frame)
        assert not frame.has("result.value")


@pytest.mark.asyncio
async def test_nested_logs_mask_before_reading_and_show_projection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Masked whole-record fields never invoke a hostile attribute getter."""
    from lclang.workflow.logging import mapping_message
    from lclang.workflow.mappings import mapping_text

    class GuardedOptions(Options):
        def __getattribute__(self, name: str) -> Any:
            if name == "encoding":
                raise AssertionError("secret must not be read")
            return super().__getattribute__(name)

    source = wf.define_variable[Options]("source")
    async with lclang.define_frame(preset={"source.encoding!": "secret"}) as frame:
        context = wf.WorkflowExecutionContext(
            False, date(2026, 9, 22), True, logging.getLogger("nested"), frame,
        )
        message = mapping_message(context, (wf.TaskID("task"),), source.quote,
                                  GuardedOptions("secret", []), output=False)
        assert "*masked*" in message and "secret" not in message
        projection = source.field("encoding", str)
        text = mapping_text(Arguments(Options(projection.quote, [])), False)
        assert "options.encoding <- $source.encoding" in text
        message = mapping_message(context, (wf.TaskID("task"),),
                                  Arguments(Options(projection.quote, [])),
                                  Arguments(Options("secret", [])), output=False)
        assert "options.encoding" in message and "secret" not in message
    assert "Options <- $source" in mapping_text(source.quote, False)
    assert "str <- $source.encoding" in mapping_text(projection.quote, False)


@pytest.mark.asyncio
async def test_opaque_optional_projection_types_and_unresolved_annotations() -> None:
    """Opaque and optional fields keep their supported outer-type contracts."""
    from lclang.workflow.mappings import require_mapping

    variable = wf.define_variable[Flexible]("flexible")
    generic = wf.define_variable[Generic[int]]("generic")
    async with lclang.define_frame(preset={
        "flexible": Flexible(object()), "generic": Generic(1, [], {}, abs),
    }) as frame:
        assert isinstance(await materialize_args(
            Flexible(variable.field("value", Any).quote), frame,
        ), Flexible)
        optional = generic.field("optional", cast(Any, int | None))
        assert await materialize_args(Flexible(optional.quote), frame) == Flexible(None)
    @dataclass
    class Unresolved:
        value: int
    Unresolved.__annotations__["value"] = "MissingMappingType"
    with pytest.raises(TypeError, match="annotations cannot be resolved"):
        require_mapping(Unresolved(1), "argument")


@pytest.mark.asyncio
async def test_invalid_verbose_resource_keeps_original_error() -> None:
    """Verbose output reporting cannot replace an invalid resource error."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def wrong(
        context: wf.TaskContext, args: Options, status_mgr: wf.ExecutionStatusManager,
    ) -> AsyncIterator[Options]:
        yield cast(Options, object())

    target = wf.define_variable[Options]("target")
    scope = wf.define_context_task("scope", "Scope", wrong, Options("utf-8", []), target.quote)
    workflow = wf.define_workflow("Invalid", wf.define_task("root", "Root", context_tasks=[scope]))
    async with lclang.define_frame() as frame:
        result = await workflow.execute(wf.WorkflowExecutionContext(
            False, date(2026, 9, 22), True, logging.getLogger("nested"), frame,
        ))
        assert result.execution_status.status is wf.ExecutionStatus.ERROR
        failure = cast(wf.WorkflowException, await frame.get("__exception__"))
        assert "mapping dataclass" in str(failure.exception)


@pytest.mark.asyncio
async def test_many_nested_mappings_remain_independent() -> None:
    """Repeated executions retain templates and explicit shared leaf identities."""
    import asyncio

    variable = wf.define_variable[str]("encoding")
    template = Arguments(Options(variable.quote, []))

    async def run(index: int) -> None:
        async with lclang.define_frame(preset={"encoding": str(index)}) as frame:
            result = cast(Arguments, await materialize_args(template, frame))
            assert result.options.encoding == str(index)
            assert result.options.shared is template.options.shared

    await asyncio.gather(*(run(index) for index in range(200)))
    assert template.options.encoding is variable.quote
