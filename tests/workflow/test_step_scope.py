"""Behavioural tests for scoped workflow step handles."""

from typing import Any, cast

import pytest

from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    ExecutionStatusStep,
    ExecutionTaskType,
)

InvalidStep = cast(Any, ExecutionStatusStep)


def test_scoped_step_starts_running_and_clean_exit_succeeds() -> None:
    """A two-argument step is shared immediately and succeeds when unchanged."""
    manager = ExecutionStatusManager("release", "publish")
    handle = manager.add_step("upload", "upload artifacts")
    assert isinstance(handle, ExecutionStatusStep)
    assert manager.current.sub_tasks[0].status is ExecutionStatus.RUNNING

    with handle as step:
        assert step is handle
        assert manager.current.sub_tasks[0].status is ExecutionStatus.RUNNING
        step.update("upload signed artifacts")

    tree = manager.finalize()
    child = tree.sub_tasks[0]
    assert child.task_type is ExecutionTaskType.STEP
    assert child.status is ExecutionStatus.SUCCESS
    assert child.task_description == "upload signed artifacts"


def test_step_updates_description_status_or_both_and_preserves_status() -> None:
    """Optional update fields support every requested mutation combination."""
    manager = ExecutionStatusManager("workflow")
    with manager.add_step("skip", "optional") as skipped:
        skipped.update(status=ExecutionStatus.SKIPPED)
    with manager.add_step("fail", "work") as failed:
        failed.update("expected rejection", ExecutionStatus.FAILURE)
    with manager.add_step("rename", "old") as renamed:
        renamed.update("new")

    tree = manager.finalize()
    assert [child.status for child in tree.sub_tasks] == [
        ExecutionStatus.SKIPPED,
        ExecutionStatus.FAILURE,
        ExecutionStatus.SUCCESS,
    ]
    assert [child.task_description for child in tree.sub_tasks] == [
        "optional",
        "expected rejection",
        "new",
    ]


def test_exceptional_step_exit_records_error_and_reraises() -> None:
    """An exception overrides earlier status, records its message, and escapes."""
    manager = ExecutionStatusManager("workflow")
    handle = manager.add_step("decode", "decode input")
    with pytest.raises(ValueError, match="bad header"), handle as step:
        step.update(status=ExecutionStatus.SUCCESS)
        raise ValueError("bad header")

    tree = manager.finalize()
    child = tree.sub_tasks[0]
    assert child.status is ExecutionStatus.ERROR
    assert child.task_description == "bad header"
    assert tree.status is ExecutionStatus.ERROR


def test_step_updates_are_atomic_and_finalized_handles_are_locked() -> None:
    """Invalid updates change nothing and every later handle operation is rejected."""
    manager = ExecutionStatusManager("workflow")
    handle = manager.add_step("work", "original")
    with pytest.raises(TypeError, match="description"):
        InvalidStep.update(handle, 1, ExecutionStatus.FAILURE)
    assert manager.current.sub_tasks[0].status is ExecutionStatus.RUNNING
    assert manager.current.sub_tasks[0].task_description == "original"
    with pytest.raises(TypeError, match="status"):
        InvalidStep.update(handle, "changed", "SUCCESS")
    assert manager.current.sub_tasks[0].task_description == "original"

    with handle:
        handle.update()
    for operation in (handle.__enter__, handle.update):
        with pytest.raises(RuntimeError, match="finalized"):
            operation()
    with pytest.raises(RuntimeError, match="finalized"):
        handle.__exit__(None, None, None)


def test_explicit_status_steps_remain_compatible_and_return_handles() -> None:
    """The original three-argument form keeps its status and can be ignored."""
    manager = ExecutionStatusManager("workflow")
    handle = manager.add_step("done", "already complete", ExecutionStatus.SUCCESS)
    assert isinstance(handle, ExecutionStatusStep)
    tree = manager.finalize()
    assert tree.sub_tasks[0].status is ExecutionStatus.SUCCESS


def test_unclosed_scoped_step_remains_unfinished_for_parent_finalization() -> None:
    """A handle not exited retains the existing running-to-failure rule."""
    manager = ExecutionStatusManager("workflow")
    manager.add_step("orphan", "started")
    tree = manager.finalize()
    assert tree.sub_tasks[0].status is ExecutionStatus.FAILURE
    assert tree.sub_tasks[0].task_description == "started (did not finish)"
