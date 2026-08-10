# M601: workflow execution status trees

## Contract

`ExecutionStatusManager` builds an ordered tree of workflow tasks and steps.
Managers returned for sub-tasks point into the same tree, so their updates are
visible through the original manager. A step is always a leaf.

Finalization recursively settles one manager's current subtree. A running node
becomes a failure and gains the suffix ` (did not finish)`. Error, failure,
pending, and clean child results propagate to task parents in that order. An
explicit error or failure is sticky against less severe results. All-skipped
children produce a skipped parent; otherwise a clean mixture containing success
produces success. Pending leaves remain pending.

Finalizing a subtree locks it against later manager operations. A parent remains
editable after a child is finalized, and finalizing the parent accepts and locks
that already-finalized child. Context-manager exit finalizes automatically.
Exceptional exit first records `ERROR` and the exception message, then propagates
the original exception.

## Public interfaces

The `pylcl.workflow` package exports:

- `ExecutionStatus`, a `StrEnum` with `PENDING`, `SUCCESS`, `FAILURE`, `ERROR`,
  `SKIPPED`, and `RUNNING` uppercase string values.
- `ExecutionTaskType`, a `StrEnum` with `TASK` and `STEP` uppercase string values.
- `ExecutionStatusTree(status, task_type, task_name, task_description,
  sub_tasks=[])`, the mutable tree value.
- `ExecutionStatusManager(name, description='', task_type=TASK,
  status=PENDING)`.
- `manager.update(status, description=None) -> None`.
- `manager.add_step(name, description, status=RUNNING) -> ExecutionStatusStep`,
  extended by M602 while retaining the explicit-status call form.
- `manager.add_sub_task(name, description, status=PENDING) ->
  ExecutionStatusManager`.
- `manager.finalize() -> ExecutionStatusTree`.

`ExecutionStatusManager` is a synchronous context manager. `__enter__` returns
the same manager, and `__exit__` never suppresses an exception.

When a child determines or escalates its parent, the parent description gains
` (sub-task '<name>' ended with <STATUS>)`. Only the first direct child with the
winning severity is named. Child ordering is insertion ordering.

## Failure behaviour

- Non-text names/descriptions and non-enum status/task types raise `TypeError`.
- Empty task names raise `ValueError`.
- Tree children must be `ExecutionStatusTree` values, and steps cannot own
  children.
- Adding children through a step manager raises `ValueError`.
- Updating, adding to, entering, or directly finalizing a locked manager raises
  `RuntimeError`.
- An exception raised inside `with manager.add_sub_task(...) as child` is retained:
  the child description becomes `str(exception)`, its status becomes `ERROR`, the
  subtree is finalized, and the same exception leaves the scope.

## Test cases

- Defaults, updates, ordered steps, and shared sub-task mutation.
- Clean, pending, unfinished, failed, and errored aggregation.
- Nested severity escalation and deterministic first-cause descriptions.
- Child finalization followed by parent additions and whole-tree locking.
- Normal and exceptional context-manager finalization and exception propagation.
- Invalid public values, step children, and every locked-manager operation.

## Acceptance

- RED: `venv\Scripts\python.exe -m pytest tests\workflow -q --no-cov` fails
  because `pylcl.workflow` does not exist.
- GREEN: the focused workflow tests pass.
- VERIFIED: `venv\Scripts\python.exe -m scripts.quality` and
  `git diff --check` pass.
