"""Dependency display uses real execution paths and compact cached leaves."""

import asyncio

import pytest

from lclang.error import LclError
from lclang.lang import LCL_BUILTINS, define_frame, define_module
from lclang.lang.engine.evaluator.display_capture import capture_runtime_display
from lclang.logger import use_verbose
from tests.logger.verbose_support import capture_logger


@pytest.mark.asyncio
async def test_static_tree_sorts_dependencies_and_cached_tree_is_a_leaf() -> None:
    """Inspection renders all static children before evaluation and stops at cache."""
    async with define_frame(
        define_module("example", {"total": "zeta + alpha", "zeta": "3", "alpha": "2"})
    ) as frame:
        before = frame.inspect_variable("total").to_lines()
        assert before[0].startswith("total: zeta + alpha (")
        assert "├─ alpha:" in before[1] and "└─ zeta:" in before[2]
        assert await frame.get("total") == 5
        tree = frame.inspect_variable("total")
        assert tree.dependencies
        assert tree.to_lines() == ["total: (int) 5 (cached)"]
        assert tree.to_lines(depth=1, prefix="* ") == ["  * total: (int) 5 (cached)"]


@pytest.mark.asyncio
async def test_failure_tree_has_nested_path_and_inline_reason() -> None:
    """A failed dependency expands once and cached returns retain the original ID."""
    logger, output = capture_logger()
    async with define_frame(
        define_module("failure", {"RESULT": "total + 1", "total": "subtotal / divisor"}),
        preset={"subtotal": 39, "divisor": 0},
    ) as frame:
        with use_verbose(logger), pytest.raises(LclError) as caught:
            await frame.get("RESULT")
        text = str(caught.value)
        assert "[LCL131421:" in text.splitlines()[0]
        assert "division by zero" in text.splitlines()[0]
        assert "RESULT: total + 1 (" in text
        assert "└─ total: subtotal / divisor (" in text
        assert "Cause:" not in text and "Reason:" not in output.getvalue()
        with use_verbose(logger), pytest.raises(LclError) as cached:
            await frame.get("total")
        assert cached.value is caught.value
        assert f"failure {caught.value.verbose_failure_id}" in text


@pytest.mark.asyncio
async def test_success_verbose_has_one_actual_sorted_root_tree() -> None:
    """Inactive branches never become runtime tree children."""
    logger, output = capture_logger()
    async with define_frame(
        define_module("run", {"RESULT": "zeta + alpha if true else unused", "zeta": "3"}),
        preset={"alpha": 2},
    ) as frame:
        with use_verbose(logger):
            assert await frame.get("RESULT") == 5
        text = output.getvalue()
        assert text.count("Evaluation tree for RESULT") == 1
        tree = text.split("Evaluation tree for RESULT", 1)[1]
        assert "├─ alpha: (int) 2 (external)" in tree
        assert "└─ zeta: 3 (" in tree
        assert "unused:" not in tree


@pytest.mark.asyncio
async def test_repeated_inline_calls_and_binding_reads_keep_actual_call_structure() -> None:
    """Repeated calls remain distinct while repeated binding reads appear once per parent."""
    async with define_frame(
        define_module("calls", {"RESULT": "((x) -> x + x)(z) + ((x) -> x)(z)", "z": "2"})
    ) as frame:
        with capture_runtime_display() as capture:
            assert await frame.get("RESULT") == 6
        text = "\n".join(capture.to_lines())
        assert text.count("z:") == 1
        assert text.count("x: (int) 2 (argument)") == 2
        assert "Result: (int) 6" in text
        with capture_runtime_display() as cached:
            assert await frame.get("RESULT") == 6
        assert cached.to_lines() == ["RESULT: (int) 6 (cached)"]


@pytest.mark.asyncio
async def test_named_function_creation_merges_into_each_actual_invocation() -> None:
    """A function binding becomes its call node and repeated invocations stay distinct."""
    async with define_frame(
        define_module("calls", {"RESULT": "apply(1) + apply(2)", "apply": "(x) -> x + 1"})
    ) as frame:
        with capture_runtime_display() as capture:
            assert await frame.get("RESULT") == 5
        text = "\n".join(capture.to_lines())
        assert text.count("apply: x + 1 (") == 2
        assert "x: (int) 1 (argument)" in text
        assert "x: (int) 2 (argument)" in text
        assert "apply: (x) ->" not in text


@pytest.mark.asyncio
async def test_native_runtime_and_static_value_leaves_share_payloads() -> None:
    """Native source labels use the reviewed builtin adapter rather than Python addresses."""
    logger, output = capture_logger()
    with capture_runtime_display() as capture, use_verbose(logger):
        value = await LCL_BUILTINS.get("recursive")
    assert value is LCL_BUILTINS.values["recursive"]
    assert capture.to_lines() == [repr(LCL_BUILTINS.inspect_variable("recursive"))]
    assert "Builtin Function: recursive" in output.getvalue() and "0x" not in output.getvalue()


@pytest.mark.asyncio
async def test_logger_disabled_during_await_skips_final_tree_and_value_repr() -> None:
    """A changed application threshold suppresses rendering after the operation resumes."""
    entered, release = asyncio.Event(), asyncio.Event()
    logger, output = capture_logger()

    class Observed:
        calls = 0

        def __repr__(self) -> str:
            self.calls += 1
            return "observed"

    value = Observed()

    async def delayed() -> Observed:
        entered.set()
        await release.wait()
        return value

    async with define_frame(
        define_module("await", {"RESULT": "delayed()"}), preset={"delayed": delayed}
    ) as frame:
        with use_verbose(logger):
            task = asyncio.create_task(frame.get("RESULT"))
            await entered.wait()
            logger.disabled = True
            release.set()
            assert await task is value
        assert value.calls == 0
        assert "Evaluation tree" not in output.getvalue()
        assert await frame.get("RESULT") is value


@pytest.mark.asyncio
async def test_concurrent_root_trees_isolate_shared_results_and_cancelled_capture() -> None:
    """Independent roots capture new work or shared leaves, and cancellation releases capture."""
    entered, shared, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = 0

    async def delayed() -> int:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return 3

    async def before() -> int:
        shared.set()
        return 2

    async def read(frame_name: str) -> tuple[int, list[str]]:
        with capture_runtime_display() as capture:
            result = await frame.get(frame_name)
        assert isinstance(result, int)
        return result, capture.to_lines()

    async with define_frame(
        define_module(
            "shared", {"RESULT": "slow + 1", "OTHER": "before() + slow", "slow": "delayed()"}
        ),
        preset={"delayed": delayed, "before": before},
    ) as frame:
        first = asyncio.create_task(read("RESULT"))
        await entered.wait()
        second = asyncio.create_task(read("OTHER"))
        await shared.wait()
        release.set()
        (value, first_lines), (other, second_lines) = await asyncio.gather(first, second)
        assert (value, other, calls) == (4, 5, 1)
        assert any("slow: delayed() (" in line for line in first_lines)
        assert any("slow: (int) 3 (shared)" in line for line in second_lines)
        assert not any("delayed:" in line for line in second_lines)

    entered.clear()
    release.clear()
    async with define_frame(
        define_module("cancel", {"RESULT": "delayed()"}), preset={"delayed": delayed}
    ) as frame:
        with capture_runtime_display() as cancelled:
            task = asyncio.create_task(frame.get("RESULT"))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert cancelled.tree is None and cancelled.result is None
        release.set()
        with capture_runtime_display() as restored:
            assert await frame.get("RESULT") == 3
        assert restored.tree is not None
