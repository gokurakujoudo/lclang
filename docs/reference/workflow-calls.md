# Calling workflows from task actions

Use `Workflow.execute_in_task(context, status_mgr, name=..., preset=...)` when
an action discovers its work items at runtime. It returns an **asynchronous
context manager**. Entering the scope executes the child workflow to completion
and yields its native `WorkflowExecutionResult`; leaving closes the owned Frame.
Use ordinary declared children when the task structure is known in advance.

## Input, result and lifetime

Each call creates a fresh Frame with the standard runtime and explicit `preset`
bindings. It inherits the parent's dry-run flag, effective date, verbosity and
logger. It does not inherit parent configuration, variables, cached values or
outputs. Bindings are shallow: explicitly passed mutable objects remain shared.
The workflow's own `lcl_mixin` has the same precedence as direct `execute` and
overrides an identically named preset binding.

The returned `task_args` and `task_outputs` contain only values actually
materialized by execution. They remain available after scope exit. The
`execution_frame` is usable **inside** the `async with` body and closed afterward.
Resources referenced by retained values may consequently be closed too.
Task Context resources already leave their normal scopes before the child
execution returns; this API does not extend those scopes.

This ownership differs from direct `Workflow.execute`, which borrows a
caller-owned Frame and never closes that Frame. Child output bindings stay in
the child Frame. Return a summary from the parent action and use its normal
`outputs_mapping` to publish selected results to the parent workflow.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

import lclang
import lclang.workflow as wf


@dataclass
class Item:
    value: int


@dataclass
class Batch:
    values: list[int]


@dataclass
class Summary:
    total: int


async def increment(
    context: wf.TaskContext, args: Item, status_mgr: wf.ExecutionStatusManager,
) -> Item:
    return Item(args.value + 1)


child = wf.define_workflow("Increment one item", wf.define_task(
    "increment", "Increment", task_action=increment,
    args_mapping=Item(wf.define_variable[int]("source").quote),
    outputs_mapping=Item(wf.define_variable[int]("target").quote),
))


async def process_batch(
    context: wf.TaskContext, args: Batch, status_mgr: wf.ExecutionStatusManager,
) -> Summary:
    total = 0
    for index, value in enumerate(args.values):
        async with child.execute_in_task(
            context, status_mgr, name=f"item-{index}", preset={"source": value},
        ) as result:
            assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
            total += await result.execution_frame.get("target")
        assert result.execution_frame.closed
        assert result.task_outputs[wf.TaskID("increment")] == Item(value + 1)
    return Summary(total)


async def main() -> None:
    workflow = wf.define_workflow("Batch", wf.define_task(
        "batch", "Process batch", task_action=process_batch,
        args_mapping=Batch([1, 2, 3]),
        outputs_mapping=Summary(wf.define_variable[int]("total").quote),
    ))
    async with lclang.define_frame() as frame:
        result = await workflow.execute(wf.WorkflowExecutionContext(
            False, date(2026, 9, 23), False, logging.getLogger("batch-calls"), frame,
        ))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        assert await frame.get("total") == 9
        assert not frame.has("target")
        assert len(result.execution_status.sub_tasks[0].sub_tasks) == 3


asyncio.run(main())
```

Each unique `item-N` node belongs to the running parent task. The same child
definition executes against separate inputs and Frames on every iteration.
Only `total` crosses back through the parent's explicit output mapping.

## Status and failure behavior

The call name must be nonempty and distinct from existing child status nodes,
declared children and Context Task IDs. The context must belong to an active
action and the supplied parent manager must accept new children. These checks
and preset validation happen before creating the Frame or running the workflow.
The helper supports sequential, awaited calls; it adds no scheduler, retries
or implicit parallelism.

The parent receives a detached copy of completed child status nodes. Parent
updates and finalization cannot change the returned native tree. A root task
with neither an action nor Context Tasks is omitted from the parent display;
roots with behavior or resource scopes stay visible. The result's own tree is
never flattened.

| Outcome | Result and parent behavior |
| --- | --- |
| Child `SUCCESS` | Yield native result; do not clear an earlier parent failure. |
| Child `FAILURE` or `FAILURE_COVERED` | Yield native result unchanged; raise parent severity to `FAILURE`, retaining an existing `ERROR`. |
| Child `ERROR` or unexpected ordinary execution exception | Yield an `ERROR` result and mark the parent `ERROR`. |
| Frame setup exception | Propagate the exception; mark the call and parent `ERROR`; never substitute or close the parent Frame. |
| Exception in the `async with` body | Close the child Frame, mark the call and parent `ERROR`, and propagate the exception. |
| Final Frame cleanup failure | Retain child values and task nodes, mark result/call/parent `ERROR`, and propagate the cleanup failure. |
| Cancellation or another nonordinary exception | Finish owned cleanup and propagate; do not convert it into a business result. |

A child failure does not interrupt the parent action's loop. After the action
returns its summary, normal workflow failure rules stop dependent declared
tasks. `FAILURE_COVERED` remains covered in the child result; the parent still
needs to account for unsuccessful work. Multiple ordinary body/cleanup failures
are retained in an exception group; cancellation retains associated cleanup
failures as causes. Start and completion logs include the call name, workflow
title and status, without automatically logging the preset payload.
