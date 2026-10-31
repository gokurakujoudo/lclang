# Tree workflows

## What you will learn

This chapter turns a sequence of async Python operations into a reusable,
inspectable workflow tree. You will learn how to:

- declare typed inputs and outputs with plain dataclasses;
- connect values with `TaskVar` mappings;
- inspect a workflow before running it;
- acquire a resource shared by a task and its descendants with a context task; and
- execute parent-first, depth-first against one shared Frame.

The design follows the central lclang idea: define a **strong way of working**,
then allow **flexibility within that way**. A workflow fixes the tree, mapping,
scope, status, and cleanup rules. Inside those boundaries, an action remains an
ordinary async Python function. It can call application services, add detailed
status steps, perform dry-run logic, or return any plain dataclass your program
needs.

## Define and inspect one task

Begin with one external integer and one produced integer. A `TaskVar[int]`
names each value. Its `quote` property lets the static dataclass instance double
as a field mapping while preserving the field's type for mypy.
For an optional input, pass `default=...` or `default_factory=...` to
`define_variable[T]`. The factory runs lazily once per workflow execution, and
its result is also visible to LCL expressions. A field's constructor default is
the final fallback when the named binding is absent; it never hides a failed
configuration expression. Continue to acquire and release resources in context
tasks rather than default factories.

<!-- lclang-doc-exec -->
```python
from dataclasses import dataclass

from lclang.workflow import (
    ExecutionStatusManager,
    TaskContext,
    define_task,
    define_variable,
    define_workflow,
)


@dataclass
class Inputs:
    value: int


@dataclass
class Outputs:
    value: int


source = define_variable[int]("source", "Number to double")
result = define_variable[int]("result")


async def double(
    context: TaskContext,
    args: Inputs,
    status_mgr: ExecutionStatusManager,
) -> Outputs:
    del context, status_mgr
    return Outputs(args.value * 2)


task = define_task(
    "double",
    "Double",
    task_action=double,
    args_mapping=Inputs(source.quote),
    outputs_mapping=Outputs(result.quote),
)
workflow = define_workflow("Double workflow", task)

assert workflow.to_lines() == [
    'Workflow "Double workflow"',
    '└─ task double "Double" args=Inputs{value <- $source} '
    'outputs=Outputs{value -> $result}',
]
```

The argument arrow points from `$source` into `Inputs.value`. The output arrow
points from `Outputs.value` into `$result`. Literal field values are passed
directly, and dataclass defaults fill fields that the mapping leaves at their
default. An omitted output mapping, or an ordinary value in one of its fields,
keeps that output private to the execution result.

`to_lines()` does not execute Python. It gives reviews, tests, and diagnostic
commands one deterministic description of the declared tree and its data flow.

## Add a scoped resource and a child

A context task is an async context manager around one task node. Its output is
mixed into that task's derived Frame. The wrapped action and its descendants can
use resources such as database sessions while the context remains open. Tasks
outside that subtree cannot see the resource through the shared execution Frame.
Explicit action outputs, by contrast, are mixed into the shared execution Frame
and can feed later tasks.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

from lclang.lang import define_frame
from lclang.workflow import (
    ExecutionStatus,
    ExecutionStatusManager,
    TaskContext,
    TaskID,
    WorkflowExecutionContext,
    define_context_task,
    define_task,
    define_variable,
    define_workflow,
)


@dataclass
class Values:
    value: int


@dataclass
class WorkArgs:
    source: int
    session: int


events: list[str] = []
source = define_variable[int]("source", "Starting value")
session = define_variable[int]("session")
prepared = define_variable[int]("prepared")


@asynccontextmanager
async def open_session(
    context: TaskContext,
    args: Values,
    status_mgr: ExecutionStatusManager,
) -> AsyncIterator[Values]:
    del context, status_mgr
    events.append("open")
    try:
        yield Values(args.value * 10)
    finally:
        events.append("close")


async def prepare(
    context: TaskContext,
    args: WorkArgs,
    status_mgr: ExecutionStatusManager,
) -> Values:
    del context, status_mgr
    events.append("prepare")
    return Values(args.source + args.session)


async def finish(
    context: TaskContext,
    args: WorkArgs,
    status_mgr: ExecutionStatusManager,
) -> Values:
    del context, status_mgr
    events.append("finish")
    return Values(args.source + args.session + 1)


async def audit(
    context: TaskContext,
    args: Values,
    status_mgr: ExecutionStatusManager,
) -> Values:
    del status_mgr
    assert context.frame.has("session") is False
    events.append("audit")
    return args


resource = define_context_task(
    "session_scope",
    "Open session",
    open_session,
    Values(source.quote),
    Values(session.quote),
)
child = define_task(
    "finish",
    "Finish",
    task_action=finish,
    args_mapping=WorkArgs(prepared.quote, session.quote),
)
root = define_task(
    "prepare",
    "Prepare",
    task_action=prepare,
    args_mapping=WorkArgs(source.quote, session.quote),
    outputs_mapping=Values(prepared.quote),
    context_tasks=[resource],
    children=[child],
)
outside = define_task(
    "audit",
    "Audit published output",
    task_action=audit,
    args_mapping=Values(prepared.quote),
)
workflow = define_workflow("Scoped work", define_task("run", "Run", children=[root, outside]))


async def main() -> None:
    async with define_frame(preset={"source": 2}) as frame:
        result = await workflow.execute(
            WorkflowExecutionContext(
                is_dryrun=False,
                as_of_date=date(2026, 8, 27),
                verbose_mode=False,
                logger=logging.getLogger("workflow-tutorial"),
                frame=frame,
            )
        )
        assert await frame.get("prepared") == 22
        assert frame.has("session") is False
        assert result.task_args[TaskID("finish")] == WorkArgs(22, 20)
        assert result.task_outputs[TaskID("finish")] == Values(43)
        assert result.task_outputs[TaskID("audit")] == Values(22)
        assert result.execution_status.status is ExecutionStatus.SUCCESS


asyncio.run(main())
assert events == ["open", "prepare", "finish", "close", "audit"]
```

The root derives a task Frame from the shared execution Frame. Its context reads
`source`, yields `session=20`, and mixes that resource into the task Frame.
`prepare` therefore returns `22`, which its explicit mapping publishes as
`prepared`. The child inherits the parent task Frame, so it reads both the
published `prepared=22` and the still-open `session=20`. It returns `43`.
The shared execution Frame has no `session` binding. The `audit` sibling runs
after the resource closes; it reads the published `prepared` value and verifies
that its Frame has no `session`.

The event assertion demonstrates the lifecycle. Execution enters contexts from
left to right, runs the node action, visits children depth-first, and exits
contexts in reverse order. Cleanup therefore surrounds the complete subtree and
finishes before the outside sibling runs.

## Failure boundaries

An ordinary exception marks its task as `ERROR`, stores a `WorkflowException`
under `__exception__` in the shared Frame, skips the remaining declared branch,
and unwinds active contexts. An action may instead set `FAILURE` through its
status manager for an expected rejection.

For deliberate recovery, subclass `FailureCoveringContextTask`. Its
`handle_exception` hook must complete before the failure becomes
`FAILURE_COVERED`. Covered failures remain visible and stop the remaining
siblings; they are not silently converted into success. This fixed behavior is
part of the strong format. The recovery code inside the hook is the confined
flexibility.

### Recover a failed task and stop later work

A recovery context owns the compensating action and resource cleanup. Here a
failed upload releases a reserved slot. The handler covers only the expected
failure; another exception is re-raised for the workflow to report.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from lclang.lang import define_frame
from lclang.workflow import (
    ExecutionStatus, ExecutionStatusManager, FailureCoveringContextTask,
    TaskContext, WorkflowExecutionContext, define_context_task, define_task,
    define_workflow,
)


@dataclass
class Slot:
    name: str


events: list[str] = []


class UploadRejected(Exception):
    """Report a known rejection that permits reservation compensation."""


class ReleaseReservation(FailureCoveringContextTask[Slot, Slot]):
    async def acquire(
        self, context: TaskContext, args: Slot, status_mgr: ExecutionStatusManager,
    ) -> Slot:
        events.append("reserve")
        return args

    async def handle_exception(
        self, context: TaskContext, args: Slot, status_mgr: ExecutionStatusManager,
        resource: Slot, exception: Exception,
    ) -> None:
        if not isinstance(exception.__cause__, UploadRejected):
            raise exception
        events.append(f"compensate {resource.name}")

    async def release(
        self, context: TaskContext, args: Slot, status_mgr: ExecutionStatusManager,
        resource: Slot,
    ) -> None:
        events.append(f"release {resource.name}")


async def upload(context: TaskContext, args: Slot, status_mgr: ExecutionStatusManager) -> Slot:
    raise UploadRejected("upload rejected")


async def notify(context: TaskContext, args: Slot, status_mgr: ExecutionStatusManager) -> Slot:
    events.append("notify")
    return args


async def main() -> None:
    recovery = define_context_task("recovery", "Release reservation", ReleaseReservation(), Slot("A"))
    attempt = define_task(
        "upload", "Upload", task_action=upload, args_mapping=Slot("A"),
        context_tasks=[recovery],
    )
    notification = define_task("notify", "Notify", task_action=notify, args_mapping=Slot("A"))
    root = define_task("root", "Publish", children=[attempt, notification])
    logger = logging.Logger("recovery-example")
    logger.addHandler(logging.NullHandler())
    async with define_frame() as frame:
        result = await define_workflow("Publish", root).execute(
            WorkflowExecutionContext(False, date(2026, 8, 27), False, logger, frame)
        )
    status = result.execution_status.sub_tasks[0]
    assert result.execution_status.status is ExecutionStatus.FAILURE_COVERED
    assert status.sub_tasks[0].status is ExecutionStatus.FAILURE_COVERED
    assert status.sub_tasks[1].status is ExecutionStatus.SKIPPED
    assert events == ["reserve", "compensate A", "release A"]


asyncio.run(main())
```

The action failure reaches the handler as an lclang exception whose cause is
the original `UploadRejected`. The handler selects it by type and re-raises
other failures. A successful handler and release mark the upload
`FAILURE_COVERED`. The sibling notification is skipped, so compensation does
not make the workflow successful or resume the remaining tasks. If compensation
or release fails, the diagnostic preserves the failures; see the
[exception guide](../reference/exceptions.md#failure-handling-and-release-both-fail).

### Cancel while resources are open

Cancellation is a control signal. It leaves the workflow only after entered
contexts unwind; it is not an ordinary failure for the recovery handler above.
The event below coordinates cancellation after the action starts, without a
clock-dependent delay.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

from lclang.lang import define_frame
from lclang.workflow import (
    ExecutionStatusManager, TaskContext, WorkflowExecutionContext,
    define_context_task, define_task, define_workflow,
)


@dataclass
class Resource:
    name: str


events: list[str] = []


@asynccontextmanager
async def open_resource(
    context: TaskContext, args: Resource, status_mgr: ExecutionStatusManager,
) -> AsyncIterator[Resource]:
    events.append(f"open {args.name}")
    try:
        yield args
    finally:
        events.append(f"close {args.name}")


async def main() -> None:
    started = asyncio.Event()

    async def wait_for_work(
        context: TaskContext, args: Resource, status_mgr: ExecutionStatusManager,
    ) -> Resource:
        started.set()
        await asyncio.Event().wait()
        return args

    contexts = [
        define_context_task("outer", "Outer", open_resource, Resource("outer")),
        define_context_task("inner", "Inner", open_resource, Resource("inner")),
    ]
    task = define_task(
        "run", "Run", task_action=wait_for_work, args_mapping=Resource("work"),
        context_tasks=contexts,
    )
    logger = logging.Logger("cancellation-example")
    logger.addHandler(logging.NullHandler())
    async with define_frame() as frame:
        context = WorkflowExecutionContext(False, date(2026, 8, 27), False, logger, frame)
        running = asyncio.create_task(define_workflow("Run", task).execute(context))
        await asyncio.wait_for(started.wait(), timeout=5)
        running.cancel()
        try:
            await running
        except asyncio.CancelledError:
            assert running.cancelled()
        else:
            raise AssertionError("workflow swallowed cancellation")
    assert events == ["open outer", "open inner", "close inner", "close outer"]


asyncio.run(main())
```

Both resources open before the action signals readiness. Cancellation interrupts
the wait, closes the inner and then outer resource, and reaches the caller as
`CancelledError`; the owning Frame then closes. If cleanup also fails, the
control signal remains primary and retains cleanup failures in its cause chain.
The application still owns any external transaction, rollback, or retry policy.
See [cancellation with cleanup failures](../reference/exceptions.md#cancellation-with-several-cleanup-failures)
for the diagnostic contract.

The CLI boundary preserves the same model. `workflow.to_cli(...)` exposes only
variables used before their first assignment, infers help and masking from
their declarations, and logs every reached task/context lifecycle around
ordinary action records. Each task Frame exposes its owner path as
`__task_id_branch__`; context log branches append their context ID. Errors retain
their traceback and still receive a completion record. Verbose mode adds typed,
aligned argument and output mappings.

The CLI prints the complete final status tree as one severity-aware multi-line
record. A valid configured `lunch.options` list adds a random option after a
successful workflow or `no lunch!` after a non-success; unusable lunch settings
are simply omitted.
Use `lclang.cli.scan_commands(...)` when a package publishes several commands.

## Where to go next

Use the [workflow reference](../reference/workflow.md) for exact mapping,
failure, rendering, and CLI contracts. Keep task actions small enough that their
inputs and outputs remain meaningful; a structural task with children is often
clearer than one action that hides an entire procedure.

[Previous: Scoped values and Frame evaluation](13-scoped-values-and-frame-evaluation.md) | [Next: Case Study: Energy Settlement Workflow](15-energy-settlement-workflow.md) | [Return to the series introduction](README.md)

See the [exception guide](../reference/exceptions.md) for failure families,
combined execution and cleanup diagnostics, and examples of handling selected
group members while retaining unhandled failures.
