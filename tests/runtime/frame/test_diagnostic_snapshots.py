"""Detached read evidence across functions, masking, caches, and concurrent calls."""

import asyncio
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from lclang import define_frame, define_module
from lclang.ast import LclBinary, LclConstant, LclName
from lclang.ast.operators import BinaryOperator
from lclang.config import load_config
from lclang.errors import LclEvaluationError
from lclang.runtime import Module
from lclang.types import ModuleName, VarName


class ObservedRepresentation:
    """Count representations and optionally reject diagnostic rendering."""

    def __init__(self, *, broken: bool = False) -> None:
        """Initialize observed rendering state."""
        self.calls = 0
        self.broken = broken

    def __repr__(self) -> str:
        """Record a rendering request and return or reject the representation."""
        self.calls += 1
        if self.broken:
            raise RuntimeError("representation unavailable")
        return "visible payload"


class UnprintableFailure(Exception):
    """Reject string conversion without changing the original exception identity."""

    def __str__(self) -> str:
        """Simulate an external exception with a broken display implementation."""
        raise RuntimeError("display unavailable")


@pytest.mark.asyncio
async def test_broken_native_exception_display_retains_original_cause() -> None:
    """Error presentation cannot replace an external failure with a display failure."""
    native = UnprintableFailure("original reason")

    def fail() -> object:
        """Raise the original external exception."""
        raise native

    async with define_frame(
        define_module("native", {"bad": "fail()"}), preset={"fail": fail}
    ) as frame:
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        assert failure.value.__cause__ is native
        assert "UnprintableFailure" in str(failure.value)
        assert "repr failed" in str(failure.value)


@pytest.mark.asyncio
async def test_success_does_not_render_and_failure_protects_masked_values() -> None:
    """Capturing reads is silent, and exact-name masking precedes representation."""
    public = ObservedRepresentation()
    secret = ObservedRepresentation()
    module = define_module("journal", {"ok": "[public, secret]", "bad": "[public, secret, 1 / 0]"})
    async with define_frame(module, preset={"public": public, "secret!": secret}) as frame:
        assert await frame.get("ok") == [public, secret]
        assert (public.calls, secret.calls) == (0, 0)
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        snapshot = failure.value.evaluation_context[-1]
        assert [value.name for value in snapshot.used_values] == ["public", "secret"]
        assert snapshot.used_values[1].value == "*masked*"
        assert (public.calls, secret.calls) == (1, 0)
        str(failure.value)
        str(failure.value)
        assert (public.calls, secret.calls) == (1, 0)
        with pytest.raises(FrozenInstanceError):
            snapshot.used_values[0].value = "changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_representation_failure_and_budget_preserve_original_cause() -> None:
    """Unprintable or long values cannot replace the division failure."""
    broken = ObservedRepresentation(broken=True)
    module = define_module("bounded", {"bad": "[broken, long_text, 1 / 0]"})
    async with define_frame(module, preset={"broken": broken, "long_text": "x" * 1000}) as frame:
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        values = failure.value.evaluation_context[-1].used_values
        assert "repr failed" in values[0].value
        assert len(values[1].value) <= 200
        assert isinstance(failure.value.__cause__, ZeroDivisionError)
        assert failure.value.__cause__.__traceback__ is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("expression", ["m.count / 0", 'm["count"] / 0'])
async def test_qualified_reads_keep_actual_names(expression: str) -> None:
    """Both scoped access spellings attribute successful reads to qualified leaves."""
    module = define_module("qualified", {"m.count": "5", "bad": expression})
    async with define_frame(module) as frame:
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        values = failure.value.evaluation_context[0].used_values
        assert [(value.name, value.value) for value in values] == [("m.count", "5")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("index", "exception", "reason"),
    [
        ("1", TypeError, "FrameProxy index must be text"),
        ('"missing"', AttributeError, "m.missing"),
        ('"_private"', AttributeError, "_private"),
    ],
)
async def test_invalid_qualified_indices_preserve_native_errors(
    index: str, exception: type[Exception], reason: str
) -> None:
    """Source-aware index reads retain Python's existing invalid-child contract."""
    module = define_module("qualified", {"m.count": "5", "bad": f"m[{index}]"})
    async with define_frame(module) as frame:
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        assert isinstance(failure.value.__cause__, exception)
        assert str(failure.value.__cause__) == reason
        assert failure.value.evaluation_context[0].used_values == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("masked", [False, True])
async def test_function_arguments_have_separate_protected_context(masked: bool) -> None:
    """A saved function retains its declaration's diagnostic mask on later calls."""
    key = "divide!" if masked else "divide"
    module = define_module(
        "functions", {key: "(total, count) -> total / count", "bad": "divide(5, 0)"}
    )
    async with define_frame(module) as frame:
        await frame.get("divide")
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        call = failure.value.evaluation_context[-1]
        assert call.kind == "function"
        assert [value.name for value in call.used_values] == ["total", "count"]
        assert [value.value for value in call.used_values] == (
            ["*masked*", "*masked*"] if masked else ["5", "0"]
        )
        if masked:
            assert "total / count" not in str(failure.value)
            assert "Cause: *masked*" in str(failure.value)


@pytest.mark.asyncio
async def test_repeated_function_reads_keep_last_value_at_first_position() -> None:
    """Repeated comprehension positions retain the last successful local value."""
    module = define_module("repeat", {"bad": "[x / (2 - x) for x in [0, 1, 2]]"})
    async with define_frame(module) as frame:
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        values = failure.value.evaluation_context[-1].used_values
        assert [value.name for value in values] == ["x", "x"]
        assert [value.value for value in values] == ["2", "2"]
        assert values[0].span.start.offset < values[1].span.start.offset


@pytest.mark.asyncio
async def test_short_circuit_and_recalculation_create_correct_snapshots() -> None:
    """Only selected branches appear, and recalculation replaces an old failure scene."""
    module = define_module("refresh", {"bad": "(used if flag else unused) / zero"})
    async with define_frame(module, preset={"flag": True, "used": 5, "zero": 0}) as frame:
        with pytest.raises(LclEvaluationError) as first:
            await frame.get("bad")
        original = str(first.value)
        assert "unused =" not in original
        frame.mixin({"used": 9})
        with pytest.raises(LclEvaluationError) as second:
            await frame.recalculate("bad")
        assert second.value is not first.value
        assert "used = (int) 9" in str(second.value)
        assert str(first.value) == original


@pytest.mark.asyncio
async def test_parallel_failure_snapshots_do_not_share_read_values() -> None:
    """Distinct owner tasks and independent Frames keep their own evidence."""
    module = define_module("parallel", {"a": "left / 0", "b": "right / 0"})
    async with define_frame(module, preset={"left": 1, "right": 2}) as frame:
        failures = await asyncio.gather(frame.get("a"), frame.get("b"), return_exceptions=True)
        for failure, name, value in zip(failures, ("left", "right"), ("1", "2"), strict=True):
            assert isinstance(failure, LclEvaluationError)
            reads = failure.evaluation_context[-1].used_values
            assert [(item.name, item.value) for item in reads] == [(name, value)]


@pytest.mark.asyncio
async def test_source_less_ast_uses_canonical_expression() -> None:
    """Hand-built ASTs have useful expressions without fabricated source coordinates."""
    node = LclBinary(
        left=LclName(identifier=VarName("value")),
        operator=BinaryOperator.TRUE_DIVIDE,
        right=LclConstant(value=0),
    )
    module = Module(ModuleName("manual"), {"bad": node})
    async with define_frame(module, preset={"value": 5}) as frame:
        with pytest.raises(LclEvaluationError) as failure:
            await frame.get("bad")
        assert "value / 0" in str(failure.value)
        assert '"<unknown>"' not in str(failure.value)


@pytest.mark.asyncio
async def test_file_changed_and_frame_closed_do_not_change_error_source() -> None:
    """Physical source snapshots survive file edits and runtime cleanup."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "main.lclcfg"
        path.write_text("price: 5\r\nresult: price / 0\r\n", encoding="utf-8", newline="")
        config = await load_config(path)
        async with config.to_frame() as frame:
            with pytest.raises(LclEvaluationError) as failure:
                await frame.get("result")
            original = str(failure.value)
            path.write_text("result: 42", encoding="utf-8")
        path.unlink()
        assert str(failure.value) == original
        assert "result: price / 0" in original
        assert "price = (int) 5" in original


@pytest.mark.asyncio
async def test_unicode_continuation_retains_physical_crlf_source() -> None:
    """Masked logical continuation text does not replace the original source excerpt."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "main.lclcfg"
        source = "数量: 5\r\n零: 0\r\n结果: (数量 + \\\r\n    1) / 零\r\n"
        path.write_text(source, encoding="utf-8", newline="")
        config = await load_config(path)
        async with config.to_frame() as frame:
            with pytest.raises(LclEvaluationError) as failure:
                await frame.get("结果")
            assert failure.value.span is not None
            assert failure.value.span.snapshot is not None
            assert failure.value.span.snapshot.text == source
            diagnostic = str(failure.value)
            assert "结果: (数量 + \\" in diagnostic
            assert "1) / 零" in diagnostic
            assert "数量 = (int) 5" in diagnostic
            assert "零 = (int) 0" in diagnostic
