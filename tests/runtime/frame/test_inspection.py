"""Behavioural tests for non-evaluating Frame variable inspection."""

import asyncio
from dataclasses import dataclass

import pytest

from lclang.api import LCL_BUILTIN_VALUES, LCL_BUILTINS, LCL_ROOT, LCL_RUNTIME
from lclang.ast import LclAstNode
from lclang.errors import LclClosedFrameError, LclEvaluationError, LclNameError
from lclang.lang.parser import parse_expression
from lclang.runtime import (
    Frame,
    Module,
    VariableInspectionStatus,
    VariableInspectionTree,
)
from lclang.types import FrameId, ModuleName, VarName


def module(name: str, definitions: dict[str, str]) -> Module:
    """Build a compact parsed module fixture."""
    return Module(
        ModuleName(name),
        {key: parse_expression(source) for key, source in definitions.items()},
    )


class MultilineValue:
    """Provide a deliberately multiline repr for presentation testing."""

    def __repr__(self) -> str:
        """Return two physical lines from one opaque host object."""
        return "first\nsecond"


class MultilineError(Exception):
    """Provide a deliberately multiline message for error rendering tests."""

    def __str__(self) -> str:
        """Return two physical lines from one current exception."""
        return "broken\nmessage"


@dataclass(frozen=True, slots=True)
class UnknownAstValue(LclAstNode):
    """Provide an unsupported custom AST value for repr fallback coverage."""


def test_inspection_deduplicates_direct_names_and_preserves_lexical_owners() -> None:
    """The tree keeps first-seen direct names while following evaluator ownership."""
    parent = Frame(
        module("parent", {"base": "40", "inherited": "base + 2"}),
        "parent",
    )
    child = Frame(
        module("child", {"base": "0", "total": "inherited + host + host"}),
        "child",
        values={"host": 1},
        parent=parent,
    )

    tree = child.inspect_variable("total")
    assert tree.var_name == VarName("total")
    assert tree.status is VariableInspectionStatus.NOT_EVALUATED
    assert tree.definition is child.module.definitions["total"]
    assert tree.definition_path == [FrameId("child")]
    assert tree.defined_at is child
    assert tree.current_value is None
    assert tree.current_exception is None
    assert [item.var_name for item in tree.dependencies] == [
        VarName("inherited"),
        VarName("host"),
    ]

    inherited = tree.dependencies[0]
    assert inherited.definition_path == [FrameId("child"), FrameId("parent")]
    assert inherited.defined_at is parent
    assert inherited.dependencies[0].var_name == VarName("base")
    assert inherited.dependencies[0].definition_path == [FrameId("parent")]
    assert inherited.dependencies[0].defined_at is parent
    assert repr(inherited) == (
        "inherited@child/parent: base + 2 (NotEvaluated) NoneType: None"
    )
    host = tree.dependencies[1]
    assert host.status is VariableInspectionStatus.EXTERNAL_PROVIDED
    assert host.current_value == 1
    assert host.dependencies == []
    assert repr(host) == "host@child: (ExternalProvided) int: 1"


def test_canonical_values_use_uniform_builtin_representations() -> None:
    """Every reviewed function and namespace uses one concise native grammar."""
    frame = Frame(
        module(
            "native",
            {
                "root": (
                    "len(items) + iter.first(items) + "
                    "parse_ymd(day).year + len(str(items))"
                )
            },
        ),
        values={"items": [1], "day": "20260809"},
        parent=LCL_RUNTIME,
    )
    tree = frame.inspect_variable("root")
    children = {str(item.var_name): item for item in tree.dependencies}
    assert children["len"].status is VariableInspectionStatus.NATIVE_PROVIDED
    assert repr(children["len"]).endswith(
        "(NativeProvided) Builtin Function: len"
    )
    assert children["iter"].status is VariableInspectionStatus.NATIVE_PROVIDED
    assert repr(children["iter"]).endswith(
        "(NativeProvided) Builtin Namespace: iter"
    )
    assert children["parse_ymd"].status is VariableInspectionStatus.NATIVE_PROVIDED
    assert repr(children["parse_ymd"]).endswith(
        "(NativeProvided) Builtin Function: parse_ymd"
    )
    assert children["str"].status is VariableInspectionStatus.NATIVE_PROVIDED
    assert repr(children["str"]).endswith(
        "(NativeProvided) Builtin Function: str"
    )
    assert children["items"].status is VariableInspectionStatus.EXTERNAL_PROVIDED
    rendered = "\n".join(tree.to_lines())
    assert "mappingproxy" not in rendered
    assert "0x" not in rendered

    for name in LCL_BUILTIN_VALUES:
        assert repr(LCL_BUILTINS.inspect_variable(name)).endswith(
            f"(NativeProvided) Builtin Function: {name}"
        )
    assert repr(LCL_ROOT.inspect_variable("lhs")).endswith(
        "(NativeProvided) Builtin Function: lhs"
    )
    for name in ("iter", "text", "data", "json"):
        assert repr(LCL_ROOT.inspect_variable(name)).endswith(
            f"(NativeProvided) Builtin Namespace: {name}"
        )
    native_scalar = Frame(
        module("native-scalar", {}),
        values={"answer": 42},
        native_values=True,
    )
    assert repr(native_scalar.inspect_variable("answer")).endswith(
        "(NativeProvided) int: 42"
    )

    lookalike = Frame(module("lookalike", {}), "LCL_BUILTINS", values={"len": len})
    spoofed = lookalike.inspect_variable("len")
    assert spoofed.status is VariableInspectionStatus.EXTERNAL_PROVIDED
    assert repr(spoofed) == (
        "len@LCL_BUILTINS: (ExternalProvided) "
        "builtin_function_or_method: <built-in function len>"
    )
    descendant = LCL_RUNTIME.derive(module("descendant", {}), {"local": 1})
    assert (
        descendant.inspect_variable("local").status
        is VariableInspectionStatus.EXTERNAL_PROVIDED
    )


def test_inspection_is_read_only_and_reports_missing_and_cycles_as_leaves() -> None:
    """Inspection neither runs code nor loses unresolved or cyclic branches."""
    calls = 0

    def produce() -> int:
        nonlocal calls
        calls += 1
        return 5

    frame = Frame(
        module(
            "app",
            {
                "root": "left + missing + produced",
                "left": "right",
                "right": "left",
                "produced": "produce()",
            },
        ),
        values={"produce": produce},
    )
    before = frame.dependency_snapshot("root")

    tree = frame.inspect_variable("root")

    after = frame.dependency_snapshot("root")
    assert calls == 0
    assert before == after
    assert before.dynamic_edges == ()
    assert tree.definition_path == [FrameId("frame-app")]
    cycle_leaf = tree.dependencies[0].dependencies[0].dependencies[0]
    assert cycle_leaf.var_name == VarName("left")
    assert cycle_leaf.dependencies == []
    missing = tree.dependencies[1]
    assert missing.status is VariableInspectionStatus.NOT_EVALUATED
    assert missing.definition is None
    assert missing.defined_at is frame
    assert missing.definition_path == [FrameId("frame-app")]
    assert isinstance(missing.current_exception, LclNameError)
    assert repr(missing) == (
        "missing@frame-app: <missing> (NotEvaluated) "
        "LclNameError: [LCL2001] unknown variable: missing"
    )
    produced = tree.dependencies[2]
    assert produced.status is VariableInspectionStatus.NOT_EVALUATED
    assert produced.dependencies[0].status is VariableInspectionStatus.EXTERNAL_PROVIDED
    assert produced.dependencies[0].current_value is produce


def test_inspection_deduplicates_missing_and_external_direct_names() -> None:
    """Repeated terminal names retain one complete diagnostic or value leaf."""
    marker = object()
    frame = Frame(
        module("terminals", {"root": "missing + missing + host + host"}),
        values={"host": marker},
    )

    tree = frame.inspect_variable("root")

    assert [item.var_name for item in tree.dependencies] == [
        VarName("missing"),
        VarName("host"),
    ]
    assert isinstance(tree.dependencies[0].current_exception, LclNameError)
    assert tree.dependencies[1].current_value is marker


def test_inspection_keeps_shared_variables_on_separate_branches() -> None:
    """Local deduplication never turns sibling branch descendants into a graph."""
    frame = Frame(
        module(
            "branches",
            {
                "root": "left + right",
                "left": "shared + shared",
                "right": "shared + shared",
                "shared": "1",
            },
        )
    )

    tree = frame.inspect_variable("root")

    left_shared = tree.dependencies[0].dependencies
    right_shared = tree.dependencies[1].dependencies
    assert [item.var_name for item in left_shared] == [VarName("shared")]
    assert [item.var_name for item in right_shared] == [VarName("shared")]
    assert left_shared[0] is not right_shared[0]


@pytest.mark.asyncio
async def test_inspection_reports_success_and_failure_cache_snapshots() -> None:
    """Committed results and failures are exposed without retrying either one."""
    calls = 0

    def fail() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("broken")

    frame = Frame(
        module("cache", {"good": "40 + 2", "bad": "fail()"}),
        values={"fail": fail},
    )
    assert await frame.get("good") == 42
    with pytest.raises(LclEvaluationError) as caught:
        await frame.get("bad")

    good = frame.inspect_variable("good")
    bad = frame.inspect_variable("bad")
    assert good.status is VariableInspectionStatus.CACHED
    assert good.current_value == 42
    assert good.current_exception is None
    assert bad.status is VariableInspectionStatus.CACHED
    assert bad.current_value is None
    assert bad.current_exception is caught.value
    assert repr(good) == "good@frame-cache: 40 + 2 (Cached) int: 42"
    assert repr(bad).startswith("bad@frame-cache: fail() (Cached) LclEvaluationError:")
    assert calls == 1


def test_inspection_repr_and_markdown_lines_are_compact_and_detached() -> None:
    """Presentation is stable, single-line, nested, and independently mutable."""
    frame = Frame(module("render", {"answer": "base + base", "base": "40"}))
    tree = frame.inspect_variable("answer")

    rendered = repr(tree)
    lines = tree.to_lines()
    indented = tree.to_lines(depth=1, prefix="* ")
    assert "\n" not in rendered
    assert rendered == (
        "answer@frame-render: base + base (NotEvaluated) NoneType: None"
    )
    assert lines[0] == f"- {rendered}"
    assert lines[1] == "  - base@frame-render: 40 (NotEvaluated) NoneType: None"
    assert len(lines) == 2
    assert indented[0] == f"  * {rendered}"
    lines.append("changed")
    assert "changed" not in tree.to_lines()


def test_inspection_repr_escapes_multiline_host_values() -> None:
    """Opaque value representations cannot break the one-line grammar."""
    frame = Frame(module("render", {}), values={"host": MultilineValue()})
    rendered = repr(frame.inspect_variable("host"))
    assert rendered == (
        "host@frame-render: (ExternalProvided) MultilineValue: first\\nsecond"
    )
    assert "\n" not in rendered


@pytest.mark.asyncio
async def test_inspection_renders_ast_values_as_typed_canonical_lcl_source() -> None:
    """Supported AST host/cache/native values use source while custom nodes fall back."""
    expression = parse_expression("base+2")
    function = parse_expression("(items) -> [item*2 for item in items if item]")
    frame = Frame(
        module("ast-values", {"result": "expression"}),
        values={
            "expression": expression,
            "function": function,
            "text": "base+2",
            "unknown": UnknownAstValue(),
        },
    )

    external = frame.inspect_variable("expression")
    assert external.current_value is expression
    assert repr(external) == (
        "expression@frame-ast-values: (ExternalProvided) LclBinary: base + 2"
    )
    assert "LclBinary(" not in repr(external)
    assert repr(frame.inspect_variable("function")) == (
        "function@frame-ast-values: (ExternalProvided) "
        "LclFunction: (items) -> [item * 2 for item in items if item]"
    )
    assert repr(frame.inspect_variable("text")) == (
        "text@frame-ast-values: (ExternalProvided) str: 'base+2'"
    )
    assert repr(frame.inspect_variable("unknown")).startswith(
        "unknown@frame-ast-values: (ExternalProvided) UnknownAstValue: UnknownAstValue("
    )

    assert await frame.get("result") is expression
    assert repr(frame.inspect_variable("result")) == (
        "result@frame-ast-values: expression (Cached) LclBinary: base + 2"
    )
    native = Frame(
        module("native-ast", {}),
        values={"expression": expression},
        native_values=True,
    )
    assert repr(native.inspect_variable("expression")) == (
        "expression@frame-native-ast: (NativeProvided) LclBinary: base + 2"
    )


@pytest.mark.asyncio
async def test_cached_lcl_function_uses_typed_canonical_source_repr() -> None:
    """An evaluated closure hides its resolver, evaluator, and AST internals."""
    source = (
        "(items) -> [] if not items else "
        "[item for item in items if item >= items[0]]"
    )
    frame = Frame(module("function-value", {"quicksort": source}))

    function = await frame.get("quicksort")
    rendered = repr(frame.inspect_variable("quicksort"))

    assert repr(function) == (
        "(items) -> [] if not items else "
        "[item for item in items if item >= items[0]]"
    )
    assert rendered == (
        "quicksort@frame-function-value: "
        "(items) -> [] if not items else "
        "[item for item in items if item >= items[0]] "
        "(Cached) LclFunctionValue: "
        "(items) -> [] if not items else "
        "[item for item in items if item >= items[0]]"
    )
    for leaked in ("BoundParameter", "SourceSpan", "ScopedResolver", "_evaluate"):
        assert leaked not in rendered


def test_inspection_repr_escapes_multiline_error_messages() -> None:
    """Current errors use compact type/message output with escaped line breaks."""
    frame = Frame(module("render", {"value": "1"}))
    tree = VariableInspectionTree(
        VarName("value"),
        VariableInspectionStatus.CACHED,
        frame.module.definitions["value"],
        [frame.frame_id],
        frame,
        42,
        MultilineError(),
        [],
    )
    rendered = repr(tree)
    assert rendered == "value@frame-render: 1 (Cached) MultilineError: broken\\nmessage"
    assert "int: 42" not in rendered


@pytest.mark.parametrize(
    ("depth", "prefix", "error"),
    [(-1, "- ", ValueError), (1.5, "- ", TypeError), (0, None, TypeError)],
)
def test_inspection_rendering_rejects_invalid_arguments(
    depth: object,
    prefix: object,
    error: type[Exception],
) -> None:
    """Rendering rejects ambiguous indentation and prefix inputs."""
    tree = VariableInspectionTree(
        VarName("value"),
        VariableInspectionStatus.NOT_EVALUATED,
        None,
        [FrameId("frame")],
        Frame(module("app", {}), "frame"),
        None,
        None,
        [],
    )
    with pytest.raises(error):
        tree.to_lines(depth=depth, prefix=prefix)  # type: ignore[arg-type]


def test_inspection_validates_name_parent_cycles_and_lifecycle() -> None:
    """Invalid requests fail deterministically without traversing forever."""
    frame = Frame(module("app", {}))
    with pytest.raises(TypeError, match="variable name must be a string"):
        frame.inspect_variable(42)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="variable name cannot be empty"):
        frame.inspect_variable("")
    frame.parent = frame
    with pytest.raises(ValueError, match="Frame parent cycle"):
        frame.inspect_variable("missing")


@pytest.mark.asyncio
async def test_closed_frame_rejects_inspection() -> None:
    """Inspection obeys the same lifecycle boundary as other Frame APIs."""
    frame = Frame(module("app", {"value": "1"}))
    await frame.close()
    with pytest.raises(LclClosedFrameError):
        frame.inspect_variable("value")


@pytest.mark.asyncio
async def test_inspection_does_not_await_external_values() -> None:
    """An external awaitable remains the exact opaque host object."""
    future: asyncio.Future[int] = asyncio.Future()
    frame = Frame(module("app", {}), values={"future": future})
    tree = frame.inspect_variable("future")
    assert tree.current_value is future
    assert future.done() is False
