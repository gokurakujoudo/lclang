# Track workflow execution status

`ExecutionStatusManager` records what happened during a multi-step Python
workflow. Use it when one final Boolean or exit code is not enough: operators,
logs, tests, or another API can inspect the returned tree and see which task was
skipped, which step failed, and where an unexpected exception originated.

The utility is independent of the LCL evaluator and has no third-party runtime
dependencies.

## Key concepts

- An `ExecutionStatusTree` is one result node. Its `sub_tasks` retain insertion
  order, making the tree stable for logging or serialization by an application.
- A `TASK` can contain tasks and steps. A `STEP` is always a leaf.
- A manager is a cursor. `add_sub_task()` returns another manager positioned at
  the new child, but both managers modify the same underlying tree.
- `add_step(name, description)` immediately appends a `RUNNING` step and returns
  its scoped handle. A clean scope changes an unchanged `RUNNING` step to
  `SUCCESS`; an explicit status selected inside the scope is preserved.
- `finalize()` settles and locks the current subtree. Finalizing a child does not
  lock its parent; finalizing the parent later locks the entire remaining tree.
- Both `with manager.add_sub_task(...) as child` and
  `with manager.add_step(...) as step` finalize automatically. An exception
  changes the scoped node to `ERROR`, replaces its description with the error
  message, and then continues propagating the same exception.

## Status aggregation

Finalization recursively finalizes children before their parent. `ERROR` wins
over `FAILURE`, which wins over `PENDING`. A clean scoped step changes from
`RUNNING` to `SUCCESS`; a `RUNNING` node finalized without closing its scope is
changed to `FAILURE` and gains ` (did not finish)`. If every child was skipped,
the parent is `SKIPPED`; a clean mix containing success is `SUCCESS`.

When a child causes a parent error or failure, the parent description identifies
the first direct child with that winning severity. That gives each level a
concise causal trail without flattening the tree.

## Build a successful workflow

Descriptions explain the purpose of work while statuses report its outcome.
The scoped sub-task managers finalize automatically.

<!-- pylcl-workflow-exec -->
```python
from pylcl.workflow import ExecutionStatus, ExecutionStatusManager

workflow = ExecutionStatusManager("release", "publish version 1.2.0")

with workflow.add_sub_task("verify", "run release checks") as verify:
    with verify.add_step("tests", "unit and integration tests") as tests:
        tests.update("all release tests passed")
    verify.add_step("security", "trusted-input audit", ExecutionStatus.SKIPPED)

with workflow.add_sub_task("publish", "upload artifacts") as publish:
    with publish.add_step("wheel", "upload the wheel"):
        pass
    with publish.add_step("sdist", "upload the source archive") as sdist:
        sdist.update(status=ExecutionStatus.SUCCESS)

result = workflow.finalize()
assert result.status is ExecutionStatus.SUCCESS
assert [task.task_name for task in result.sub_tasks] == ["verify", "publish"]
assert result.sub_tasks[0].task_description == "run release checks"
assert result.sub_tasks[0].sub_tasks[0].task_description == "all release tests passed"
```

The `verify` task becomes `SUCCESS` because at least one clean child succeeded;
an intentionally skipped sibling does not make the whole task skipped.

## Capture an exception without hiding it

Catch the application exception outside the managed scope when the workflow
must continue long enough to publish or log its status tree.

<!-- pylcl-workflow-exec -->
```python
from pylcl.workflow import ExecutionStatus, ExecutionStatusManager

workflow = ExecutionStatusManager("import", "load customer data")

try:
    with workflow.add_step("decode", "decode the input file") as decode:
        decode.update("validate the file header")
        raise ValueError("invalid header")
except ValueError:
    pass

result = workflow.finalize()
failed_task = result.sub_tasks[0]
assert failed_task.status is ExecutionStatus.ERROR
assert failed_task.task_description == "invalid header"
assert result.status is ExecutionStatus.ERROR
assert result.task_description == (
    "load customer data (sub-task 'decode' ended with ERROR)"
)
```

The step first receives a more precise description, but the exception message
replaces it when the scope fails. The context manager does not suppress
`ValueError`; the `except` block is still required. If the exception should
abort the caller, simply omit that block.

## Record incomplete work

Call `update()` as execution advances. If control leaves a node in `RUNNING`,
finalization exposes the incomplete work as a failure rather than silently
reporting success:

```python
workflow = ExecutionStatusManager("backup", "nightly backup")
copy = workflow.add_sub_task("copy", "copy database files")
copy.update(ExecutionStatus.RUNNING)
copy_result = copy.finalize()

assert copy_result.status is ExecutionStatus.FAILURE
assert copy_result.task_description == "copy database files (did not finish)"

# The child is locked, but its parent can still record sibling work.
workflow.add_step("notify", "send an operator alert", ExecutionStatus.SUCCESS)
result = workflow.finalize()
```

Keep the returned tree as the structured result. Applications can traverse its
plain fields to render console output, emit logs, or convert it to their own wire
format; pylcl deliberately does not impose a JSON or presentation schema.
