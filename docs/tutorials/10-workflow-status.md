# Workflow status

`ExecutionStatusManager` records a nested account of work. It is useful when a
single Boolean or exit code cannot explain which task succeeded, was skipped,
failed as expected, or stopped with an error.

## What you will learn

- how tasks and leaf steps form an ordered tree;
- how scoped steps finalize successful work automatically;
- how parent status aggregates from child outcomes;
- how exceptions are recorded without being suppressed.

## Build a successful release workflow

Descriptions explain intent; statuses explain outcome. Explicitly skipped work
can sit beside successful work without making the whole task skipped.

<!-- lclang-doc-exec -->
```python
from lclang.workflow import ExecutionStatus, ExecutionStatusManager

workflow = ExecutionStatusManager("release", "publish version 1.2.0")

with workflow.add_sub_task("verify", "run release checks") as verify:
    with verify.add_step("tests", "unit and integration tests") as tests:
        tests.update("912 tests passed")
    verify.add_step("manual", "optional manual approval", ExecutionStatus.SKIPPED)

with workflow.add_sub_task("publish", "upload artifacts") as publish:
    with publish.add_step("wheel", "upload the wheel"):
        pass
    with publish.add_step("sdist", "upload the source archive") as sdist:
        sdist.update(status=ExecutionStatus.SUCCESS)

result = workflow.finalize()
assert result.status is ExecutionStatus.SUCCESS
assert [child.task_name for child in result.sub_tasks] == ["verify", "publish"]
assert result.sub_tasks[0].sub_tasks[0].task_description == "912 tests passed"
assert [child.status for child in result.sub_tasks[0].sub_tasks] == [
    ExecutionStatus.SUCCESS,
    ExecutionStatus.SKIPPED,
]
```

Leaving each scoped running step cleanly changes it to `SUCCESS`; the manual
step keeps its explicit `SKIPPED` state. Each sub-task therefore contains at
least one success and no failure, so both become successful. Finalizing the root
applies the same aggregation and preserves the insertion order checked by the
assertions.

Children retain insertion order. A clean scoped step changes an unchanged
`RUNNING` status to `SUCCESS`. Finalization locks that subtree against later
mutation.

## Capture failure detail and incomplete work

An exception changes the scoped node to `ERROR`, uses the exception text as its
description, finalizes it, and then propagates the same exception.

<!-- lclang-doc-exec -->
```python
from lclang.workflow import ExecutionStatus, ExecutionStatusManager

workflow = ExecutionStatusManager("import", "load customer data")

try:
    with workflow.add_step("decode", "decode input") as decode:
        decode.update("validate the file header")
        raise ValueError("invalid header")
except ValueError:
    pass

copy = workflow.add_sub_task("copy", "copy accepted rows")
copy.update(ExecutionStatus.RUNNING)
copy_result = copy.finalize()
assert copy_result.status is ExecutionStatus.FAILURE
assert copy_result.task_description == "copy accepted rows (did not finish)"

result = workflow.finalize()
assert result.status is ExecutionStatus.ERROR
assert result.sub_tasks[0].task_description == "invalid header"
assert result.task_description == (
    "load customer data (sub-task 'decode' ended with ERROR)"
)
```

The `ValueError` leaves the decode scope exceptionally, replacing its current
description with `invalid header` and setting `ERROR`. The copy task is
explicitly left running, so finalization converts it to `FAILURE` and appends
the unfinished suffix. Because error outranks failure, the root reports the
decode child as its direct cause.

Aggregation severity is `ERROR`, then `FAILURE`, then `PENDING`. If every child
is skipped, the parent becomes `SKIPPED`; a clean mixture containing success
becomes `SUCCESS`. An unfinished `RUNNING` node becomes `FAILURE` with the
`(did not finish)` suffix rather than being silently accepted.

The returned tree contains ordinary typed fields. Applications may render it,
log it, or convert it to their own wire schema; lclang deliberately defines the
status semantics without forcing one presentation format.

[Previous: Command-line applications](09-command-line-applications.md) | [Next: Business-day calendars](11-business-day-calendars.md) | [Return to the series introduction](README.md)
