"""Behavioural tests for workflow execution status trees."""

from typing import Any, cast

import pytest

from pylcl.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    ExecutionStatusTree,
    ExecutionTaskType,
)

InvalidManager = cast(Any, ExecutionStatusManager)
InvalidTree = cast(Any, ExecutionStatusTree)


def test_managers_share_ordered_tree_and_clean_statuses() -> None:
    """Child cursors update one tree and clean outcomes aggregate predictably."""
    manager = ExecutionStatusManager("deploy", "release")
    skipped = manager.add_sub_task("optional", "optional checks")
    skipped.add_step("lint", "not required", ExecutionStatus.SKIPPED)
    skipped_tree = skipped.finalize()
    assert skipped_tree.status is ExecutionStatus.SKIPPED

    with manager.add_sub_task("publish", "publish artifacts") as publish:
        publish.add_step("wheel", "upload wheel", ExecutionStatus.SUCCESS)
        publish.add_step("sdist", "not selected", ExecutionStatus.SKIPPED)
    manager.add_step("notify", "send notice", ExecutionStatus.SUCCESS)

    tree = manager.finalize()
    assert tree.status is ExecutionStatus.SUCCESS
    assert tree.task_type is ExecutionTaskType.TASK
    assert tree.task_name == "deploy"
    assert tree.task_description == "release"
    assert [child.task_name for child in tree.sub_tasks] == [
        "optional",
        "publish",
        "notify",
    ]
    assert tree.sub_tasks[0] is skipped_tree
    assert tree.sub_tasks[1].status is ExecutionStatus.SUCCESS


def test_context_manager_records_error_finalizes_and_reraises() -> None:
    """Exceptional scope exit records the message without suppressing the error."""
    manager = ExecutionStatusManager("workflow")
    with (
        pytest.raises(ValueError, match="broken input") as caught,
        manager.add_sub_task("prepare", "initial text") as prepare,
    ):
        prepare.add_step("read", "read input", ExecutionStatus.SUCCESS)
        raise ValueError("broken input")

    tree = manager.finalize()
    child = tree.sub_tasks[0]
    assert str(caught.value) == "broken input"
    assert child.status is ExecutionStatus.ERROR
    assert child.task_description == "broken input"
    assert tree.status is ExecutionStatus.ERROR
    assert tree.task_description == " (sub-task 'prepare' ended with ERROR)"


def test_finalization_handles_pending_running_and_issue_severity() -> None:
    """Complex branches retain pending work and choose the first worst issue."""
    manager = ExecutionStatusManager("workflow", "daily")
    manager.add_step("failed-first", "expected failure", ExecutionStatus.FAILURE)
    manager.add_step("pending", "not started", ExecutionStatus.PENDING)
    manager.add_step("running", "started", ExecutionStatus.RUNNING)
    error = manager.add_sub_task("errored", "nested")
    error.add_step("boom", "unexpected", ExecutionStatus.ERROR)

    tree = manager.finalize()
    assert tree.status is ExecutionStatus.ERROR
    assert tree.task_description == "daily (sub-task 'errored' ended with ERROR)"
    assert tree.sub_tasks[1].status is ExecutionStatus.PENDING
    assert tree.sub_tasks[2].status is ExecutionStatus.FAILURE
    assert tree.sub_tasks[2].task_description == "started (did not finish)"
    assert tree.sub_tasks[3].task_description == (
        "nested (sub-task 'boom' ended with ERROR)"
    )


def test_explicit_failures_are_sticky_but_errors_escalate() -> None:
    """A clean child cannot erase failure while a child error still escalates it."""
    failed = ExecutionStatusManager("failed", "own", status=ExecutionStatus.FAILURE)
    failed.add_step("clean", "done", ExecutionStatus.SUCCESS)
    failed_tree = failed.finalize()
    assert failed_tree.status is ExecutionStatus.FAILURE
    assert failed_tree.task_description == "own"

    escalated = ExecutionStatusManager("failed", "own", status=ExecutionStatus.FAILURE)
    escalated.add_step("broken", "bad", ExecutionStatus.ERROR)
    escalated_tree = escalated.finalize()
    assert escalated_tree.status is ExecutionStatus.ERROR
    assert escalated_tree.task_description == "own (sub-task 'broken' ended with ERROR)"

    errored = ExecutionStatusManager("errored", "own", status=ExecutionStatus.ERROR)
    errored.add_step("failed", "bad", ExecutionStatus.FAILURE)
    errored_tree = errored.finalize()
    assert errored_tree.status is ExecutionStatus.ERROR
    assert errored_tree.task_description == "own"


def test_failure_and_pending_children_propagate_without_errors() -> None:
    """Failure and pending branches select their documented parent outcomes."""
    failed = ExecutionStatusManager("root", "work")
    failed.add_step("broken", "bad", ExecutionStatus.FAILURE)
    failed_tree = failed.finalize()
    assert failed_tree.status is ExecutionStatus.FAILURE
    assert failed_tree.task_description == "work (sub-task 'broken' ended with FAILURE)"

    pending = ExecutionStatusManager("root", status=ExecutionStatus.SUCCESS)
    pending.add_step("waiting", "later", ExecutionStatus.PENDING)
    assert pending.finalize().status is ExecutionStatus.PENDING


def test_subtree_locks_do_not_lock_parent_but_ancestor_finalize_locks_all() -> None:
    """Locks apply to the finalized subtree and later expand with its ancestor."""
    manager = ExecutionStatusManager("root")
    child = manager.add_sub_task("child", "work")
    child.update(ExecutionStatus.SUCCESS)
    child.finalize()

    locked_operations = [
        lambda: child.update(ExecutionStatus.FAILURE),
        lambda: child.add_step("late", "late", ExecutionStatus.SUCCESS),
        lambda: child.add_sub_task("late", "late"),
        child.finalize,
        child.__enter__,
    ]
    for operation in locked_operations:
        with pytest.raises(RuntimeError, match="finalized"):
            operation()

    manager.add_step("sibling", "still allowed", ExecutionStatus.SUCCESS)
    manager.finalize()
    with pytest.raises(RuntimeError, match="finalized"):
        manager.update(ExecutionStatus.SUCCESS)


@pytest.mark.parametrize(
    "factory, error",
    [
        (lambda: InvalidManager(1), TypeError),
        (lambda: InvalidManager(""), ValueError),
        (lambda: InvalidManager("task", 1), TypeError),
        (lambda: InvalidManager("task", task_type="TASK"), TypeError),
        (lambda: InvalidManager("task", status="PENDING"), TypeError),
        (
            lambda: InvalidTree(
                ExecutionStatus.PENDING,
                ExecutionTaskType.TASK,
                "task",
                "description",
                (),
            ),
            TypeError,
        ),
        (
            lambda: InvalidTree(
                ExecutionStatus.PENDING,
                ExecutionTaskType.TASK,
                "task",
                "description",
                [object()],
            ),
            TypeError,
        ),
        (
            lambda: ExecutionStatusTree(
                ExecutionStatus.PENDING,
                ExecutionTaskType.STEP,
                "step",
                "description",
                [
                    ExecutionStatusTree(
                        ExecutionStatus.SUCCESS,
                        ExecutionTaskType.STEP,
                        "child",
                        "description",
                    )
                ],
            ),
            ValueError,
        ),
    ],
)
def test_public_values_reject_invalid_shapes(factory: object, error: type[Exception]) -> None:
    """Every public scalar and structural invariant fails before tree mutation."""
    with pytest.raises(error):
        factory()  # type: ignore[operator]


def test_updates_validate_values_and_steps_remain_leaves() -> None:
    """Mutation inputs are checked and step managers cannot gain descendants."""
    manager = ExecutionStatusManager("step", task_type=ExecutionTaskType.STEP)
    with pytest.raises(ValueError, match="step"):
        manager.add_step("child", "bad", ExecutionStatus.SUCCESS)
    with pytest.raises(ValueError, match="step"):
        manager.add_sub_task("child", "bad")
    with pytest.raises(TypeError, match="status"):
        InvalidManager.update(manager, "SUCCESS")
    with pytest.raises(TypeError, match="description"):
        InvalidManager.update(manager, ExecutionStatus.SUCCESS, 1)
    task_manager = ExecutionStatusManager("task")
    with pytest.raises(TypeError, match="status"):
        InvalidManager.add_step(task_manager, "child", "bad", "SUCCESS")


def test_normal_manager_context_finalizes_its_current_tree() -> None:
    """A directly managed scope returns itself and finalizes on clean exit."""
    manager = ExecutionStatusManager("single", status=ExecutionStatus.RUNNING)
    with manager as entered:
        assert entered is manager
        entered.update(ExecutionStatus.SUCCESS, "done")
    with pytest.raises(RuntimeError, match="finalized"):
        manager.finalize()
