"""Status aggregation preserves explicit outcomes and starts scopes on entry."""

import pytest

from lclang.error import LclStateError
from lclang.workflow import ExecutionStatus, ExecutionStatusManager


def read_status(manager: ExecutionStatusManager) -> ExecutionStatus:
    """Read status after lifecycle operations have changed the tree."""
    return manager.current.status


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.PENDING,
        ExecutionStatus.SUCCESS,
        ExecutionStatus.FAILURE,
        ExecutionStatus.FAILURE_COVERED,
        ExecutionStatus.ERROR,
        ExecutionStatus.SKIPPED,
    ],
)
def test_non_running_parent_preserves_status_and_locks_child(status: ExecutionStatus) -> None:
    """Finalization preserves an explicit parent and the child's error evidence."""
    parent = ExecutionStatusManager("parent", "parent description", status=status)
    child = parent.add_sub_task("child", "child description", ExecutionStatus.ERROR)

    result = parent.finalize()

    assert result.status is status
    assert result.task_description == "parent description"
    assert result.sub_tasks[0].status is ExecutionStatus.ERROR
    assert result.sub_tasks[0].task_description == "child description"
    with pytest.raises(LclStateError, match="finalized"):
        child.update(ExecutionStatus.SUCCESS)
    with pytest.raises(LclStateError, match="finalized"):
        parent.update(ExecutionStatus.RUNNING)


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        ([ExecutionStatus.SUCCESS, ExecutionStatus.SKIPPED], ExecutionStatus.SUCCESS),
        ([ExecutionStatus.SKIPPED], ExecutionStatus.SKIPPED),
        ([ExecutionStatus.PENDING, ExecutionStatus.SUCCESS], ExecutionStatus.PENDING),
        (
            [ExecutionStatus.FAILURE_COVERED, ExecutionStatus.SUCCESS],
            ExecutionStatus.FAILURE_COVERED,
        ),
        ([ExecutionStatus.FAILURE_COVERED, ExecutionStatus.FAILURE], ExecutionStatus.FAILURE),
        ([ExecutionStatus.FAILURE, ExecutionStatus.ERROR], ExecutionStatus.ERROR),
    ],
)
def test_running_parent_aggregates_children(
    children: list[ExecutionStatus], expected: ExecutionStatus
) -> None:
    """Running parents select the most severe child and retain every result."""
    parent = ExecutionStatusManager("parent", status=ExecutionStatus.RUNNING)
    for index, child_status in enumerate(children):
        parent.add_step(f"step-{index}", "child", child_status)

    result = parent.finalize()

    assert result.status is expected
    assert [child.status for child in result.sub_tasks] == children


def test_entering_default_manager_starts_it_without_starting_children() -> None:
    """A scope starts on entry, while adding a child does not start either node."""
    parent = ExecutionStatusManager("parent")
    child = parent.add_sub_task("child", "not started")
    assert read_status(parent) is ExecutionStatus.PENDING
    assert read_status(child) is ExecutionStatus.PENDING

    with parent:
        assert read_status(parent) is ExecutionStatus.RUNNING
        assert read_status(child) is ExecutionStatus.PENDING
        with child:
            assert read_status(child) is ExecutionStatus.RUNNING
            child.add_step("done", "completed", ExecutionStatus.SUCCESS)

    assert read_status(child) is ExecutionStatus.SUCCESS
    assert read_status(parent) is ExecutionStatus.SUCCESS


def test_explicit_success_survives_ancestor_finalization() -> None:
    """An ancestor keeps a handled child error in the tree without restoring it."""
    root = ExecutionStatusManager("root", status=ExecutionStatus.RUNNING)
    recovered = root.add_sub_task("recovered", "handled", ExecutionStatus.SUCCESS)
    recovered.add_sub_task("failed", "original error", ExecutionStatus.ERROR)

    result = root.finalize()

    assert result.status is ExecutionStatus.SUCCESS
    assert result.sub_tasks[0].status is ExecutionStatus.SUCCESS
    assert result.sub_tasks[0].sub_tasks[0].status is ExecutionStatus.ERROR


def test_empty_manager_scope_finishes_successfully() -> None:
    """Entering and leaving a pending manager completes the work it started."""
    manager = ExecutionStatusManager("empty")
    with manager:
        assert read_status(manager) is ExecutionStatus.RUNNING
    assert read_status(manager) is ExecutionStatus.SUCCESS
