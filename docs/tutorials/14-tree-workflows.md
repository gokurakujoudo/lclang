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

import lclang.workflow as wf


@dataclass
class Inputs:
    value: int


@dataclass
class Outputs:
    value: int


source = wf.define_variable[int]("source", "Number to double")
result = wf.define_variable[int]("result")


async def double(
    context: wf.TaskContext,
    args: Inputs,
    status_mgr: wf.ExecutionStatusManager,
) -> Outputs:
    del context, status_mgr
    return Outputs(args.value * 2)


task = wf.define_task(
    "double",
    "Double",
    task_action=double,
    args_mapping=Inputs(source.quote),
    outputs_mapping=Outputs(result.quote),
)
workflow = wf.define_workflow("Double workflow", task)

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
mixed only into that task's derived Frame. This makes resources such as database
sessions available to the wrapped action without publishing them to siblings.
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

import lclang
import lclang.workflow as wf


@dataclass
class Values:
    value: int


@dataclass
class WorkArgs:
    source: int
    session: int


events: list[str] = []
source = wf.define_variable[int]("source", "Starting value")
session = wf.define_variable[int]("session")
prepared = wf.define_variable[int]("prepared")


@asynccontextmanager
async def open_session(
    context: wf.TaskContext,
    args: Values,
    status_mgr: wf.ExecutionStatusManager,
) -> AsyncIterator[Values]:
    del context, status_mgr
    events.append("open")
    try:
        yield Values(args.value * 10)
    finally:
        events.append("close")


async def prepare(
    context: wf.TaskContext,
    args: WorkArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> Values:
    del context, status_mgr
    events.append("prepare")
    return Values(args.source + args.session)


async def finish(
    context: wf.TaskContext,
    args: Values,
    status_mgr: wf.ExecutionStatusManager,
) -> Values:
    del context, status_mgr
    events.append("finish")
    return Values(args.value + 1)


resource = wf.define_context_task(
    "session_scope",
    "Open session",
    open_session,
    Values(source.quote),
    Values(session.quote),
)
child = wf.define_task(
    "finish",
    "Finish",
    task_action=finish,
    args_mapping=Values(prepared.quote),
)
root = wf.define_task(
    "prepare",
    "Prepare",
    task_action=prepare,
    args_mapping=WorkArgs(source.quote, session.quote),
    outputs_mapping=Values(prepared.quote),
    context_tasks=[resource],
    children=[child],
)
workflow = wf.define_workflow("Scoped work", root)


async def main() -> None:
    async with lclang.define_frame(preset={"source": 2}) as frame:
        result = await workflow.execute(
            wf.WorkflowExecutionContext(
                is_dryrun=False,
                as_of_date=date(2026, 8, 27),
                verbose_mode=False,
                logger=logging.getLogger("workflow-tutorial"),
                frame=frame,
            )
        )
        assert await frame.get("prepared") == 22
        assert frame.has("session") is False
        assert result.task_args[wf.TaskID("finish")] == Values(22)
        assert result.task_outputs[wf.TaskID("finish")] == Values(23)
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS


asyncio.run(main())
assert events == ["open", "prepare", "finish", "close"]
```

The root derives a task Frame from the shared execution Frame. Its context reads
`source`, yields `session=20`, and mixes that resource into the task Frame.
`prepare` therefore returns `22`, which its explicit mapping publishes as
`prepared`. The child derives a fresh Frame directly from the shared execution
Frame: it cannot see `session`, but it can read the published `prepared` value.

The event assertion demonstrates the lifecycle. Execution enters contexts from
left to right, runs the node action, visits children depth-first, and exits
contexts in reverse order. Cleanup therefore surrounds the complete subtree.

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
