# Tree Workflow API

## Design model

`lclang.workflow` follows the same separation as Modules and Frames. A workflow
is a strong reusable format: an immutable tree of valid task IDs, typed
dataclass boundaries, explicit variable flows, ordered contexts, and ordered
children. `Workflow.execute` supplies flexibility only inside that format:
actions are ordinary async Python, contexts may own arbitrary dismissible
resources, and status managers may add run-specific detail.

The definition never owns execution state. One execution borrows a shared
`Frame`, derives short-lived task Frames, records argument and output values,
and creates a fresh status tree. Reusing a `Workflow` is therefore analogous to
reusing a `Module`; each call is analogous to creating a new per-run `Frame`.

`define_workflow(title, root_task, lcl_mixin=None)` accepts a `dict[str, Any]`
of host values and callables, for example `lcl_mixin={"service": service}`.
The mapping is copied shallowly when defined; objects remain shared by reference.
Qualified names and trailing `!` masking markers follow normal Frame rules.
Invalid names and conflicting scopes fail at definition time.

Direct `execute` mixes these bindings into the borrowed shared Frame before any
task starts. They override existing bindings and remain in that Frame afterward.
Configuration expressions, context tasks, and actions resolve them through the
same Frame hierarchy. Existing cached dependants remain snapshots; mixins do not
invalidate them. Task outputs may subsequently replace the supplied bindings.

For `to_cli`, these bindings instead seed the command's host preset before
configuration evaluation and logger setup. Explicit `to_cli(preset=...)` values,
configuration definitions, and CLI overrides retain their normal precedence over
these defaults. Only inferred external task variables remain CLI parameters;
extra host helpers do not become parameters. Dynamic `using` targets retain the
loader's existing scope and do not receive command host presets.

## Variables and mappings

See [variable types and boxes](workflow-types.md) and
[mapping shapes and best practices](workflow-mappings.md) for supported
annotations, conversion costs and complete examples of each mapping shape.

Variables accept mutually exclusive `default=` and `default_factory=` keywords.
Omission differs from an explicit `default=None`; an explicitly supplied
`default_factory` must be callable. Defaults are lower priority than all
effective configuration, CLI, preset and host bindings. They are available to
both mapping resolution and LCL expressions during execution. A missing quote
may finally use its dataclass field default; a failed existing definition never
falls back. Factories accept no arguments, may return an awaitable, and run only
on first use, sharing one result or failure per execution. Fixed default values
retain identity; use factories for independent mutable values. Help displays
factory metadata without invoking factories. Reuse a fresh Frame when new
dependency values are needed: cached expressions remain snapshots.

Mappings recursively resolve dataclass fields, including nested whole-record
quotes. Containers, callbacks, and concrete referenced records retain their
identity. Mapping templates are not mutated. Cyclic templates are rejected;
reusing an acyclic nested template is supported. Output extraction validates
the complete structure and target set before publishing one atomic update.

`variable.field("name", FieldType).quote` reads a declared dataclass field.
Projections may be chained, remain read-only, and retain the original variable's
dependency and masking metadata. Missing fields, incompatible declared types,
and null intermediate values report their mapping and variable paths. CLI
inference, static trees and verbose logs follow the same recursive structure.
Runtime validation checks record structure and reference contracts, not every
ordinary value or container element. `FrameProxy.as_record()` remains shallow;
recursive conversion is specific to workflow mappings.

Create variables through the subscribed factory:

```python
import lclang.workflow as wf

source = wf.define_variable[int]("source", "Required source value")
secret = wf.define_variable[str]("service.token", "Service token", is_masked=True)
result = wf.define_variable[float]("result")
```

The subscription accepts Python type annotations, including `list[str]`,
`Mapping[str, int]`, `Callable[[str], int]`, unions, and generic dataclasses such
as `Record[int]`. The resulting `.quote` retains that exact static type.

An entire argument or output mapping may also be a dataclass variable's
`.quote`. Its declared type must exactly match the callable's corresponding
annotation (including generic arguments); non-dataclass variables cannot be
whole mappings. The keyword remains `outputs_mapping` for output publication.
These rules apply to actions and context tasks alike.

`args_mapping=var.quote` reads just `var.name` from the task Frame. A stored
dataclass is passed through; a scope proxy is materialized using `as_record`
with the declared dataclass type. Conversion is recursive, preserves constructor
defaults, and reports missing required fields or failed field expressions.
Runtime checks validate the dataclass class, not its individual field types.

`outputs_mapping=var.quote` publishes the returned dataclass under `var.name`.
If that name already denotes a scope in the destination Frame, its direct
dataclass fields instead become `var.name.field` bindings in one mixin update.
This is shallow publication, not recursive `asdict` conversion: nested values
retain their identity, and unrelated existing scope fields remain unchanged.
Action outputs target the shared Frame; context outputs target the task Frame.
Whole-variable masking also masks every field published into a scope.
Whole mappings participate in static trees, verbose logs, and CLI input
inference as the named variable; existing per-field mappings remain supported.
The existing output target is resolved to determine whether it is a proxy;
resolution errors use the normal workflow error path without publishing fields.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

import lclang
import lclang.workflow as wf


@dataclass
class Batch[T]:
    items: list[T]


async def copy_batch(
    context: wf.TaskContext,
    args: Batch[str],
    status_mgr: wf.ExecutionStatusManager,
) -> Batch[str]:
    return args


async def main() -> None:
    source = wf.define_variable[Batch[str]]("source")
    target = wf.define_variable[Batch[str]]("target")
    task = wf.define_task(
        "copy", "Copy batch", task_action=copy_batch,
        args_mapping=source.quote, outputs_mapping=target.quote,
    )
    workflow = wf.define_workflow("Batch copy", task)
    async with lclang.define_frame(
        preset={"source.items": ["a", "b"], "target.items": []},
    ) as frame:
        result = await workflow.execute(wf.WorkflowExecutionContext(
            False, date(2026, 9, 21), False, logging.getLogger("batch-example"), frame,
        ))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        assert result.task_args[wf.TaskID("copy")] == Batch(["a", "b"])
        assert await frame.get("target.items") == ["a", "b"]


asyncio.run(main())
```

The qualified input creates a `source` scope. The whole argument mapping reads
its `items` child into `Batch[str]`, and the action returns that record. Since
`target` is also a scope, publication updates `target.items`. Without the
initial `target.items` binding, publication would instead store the record at
`target`. In both cases the task result retains the returned dataclass.

`TaskVar.quote` is statically typed as the represented value but returns the
variable marker at runtime. It can therefore occupy a normally typed dataclass
field in a definition mapping. Nested argument fields containing a marker are resolved
from the current task Frame. Other fields retain their literal value, including
values supplied by dataclass defaults.

Output publication is opt-in. With no output mapping, nothing is published.
Within a mapping, only fields containing `TaskVar.quote` are copied from the
returned dataclass into a Frame; other fields are retained in `task_outputs`
but remain unmapped. Masked variables use the same exact-name redaction model
as Modules, Presets, configuration, CLI bindings, and Frame mixins.

### Grouped arguments and projections

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

import lclang
import lclang.workflow as wf


@dataclass
class FormatOptions:
    encoding: str


@dataclass
class ConvertArgs:
    options: FormatOptions


async def convert(
    context: wf.TaskContext,
    args: ConvertArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> ConvertArgs:
    return args


async def main() -> None:
    source = wf.define_variable[FormatOptions]("source")
    target = wf.define_variable[str]("target.encoding")
    task = wf.define_task(
        "convert", "Resolve grouped options", task_action=convert,
        args_mapping=ConvertArgs(FormatOptions(source.field("encoding", str).quote)),
        outputs_mapping=ConvertArgs(FormatOptions(target.quote)),
    )
    workflow = wf.define_workflow("Grouped conversion", task)
    async with lclang.define_frame(preset={"source.encoding": "utf-8"}) as frame:
        result = await workflow.execute(wf.WorkflowExecutionContext(
            False, date(2026, 9, 22), False, logging.getLogger("grouped"), frame,
        ))
        assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
        assert await frame.get("target.encoding") == "utf-8"
        assert result.task_args[wf.TaskID("convert")] == ConvertArgs(FormatOptions("utf-8"))


asyncio.run(main())
```

The projection materializes the source record from its scope, then reads its
encoding field. The nested argument template becomes a separate record; the
returned nested field publishes to the explicitly selected target. CLI analysis
recognizes the projection's original `source` variable as the input, while the
output remains an assigned value.

## Tasks and contexts

An action has the exact async form:

```python
async def action(
    context: wf.TaskContext,
    args: Args,
    status_mgr: wf.ExecutionStatusManager,
) -> Outputs:
    ...
```

`Args` and `Outputs` are dataclasses with plain annotated fields. lclang checks
the callable boundary and dataclass shape but deliberately does not impose
runtime field validation. Application code remains responsible for semantic
types received from external systems.

Each TaskNode may have ordered context tasks and ordered child tasks. Context
factories accept the same three arguments and return an async context manager.
They enter left-to-right before the action and exit right-to-left after all
children. Their mapped resources enter the owning task Frame. Child task Frames derive
from their parent task Frame, so these resources remain visible throughout the
owned subtree and do not leak to outside sibling branches. Mapped action outputs enter the shared Frame and
are visible to later parent-first, depth-first tasks.

Each derived task-node Frame contains `__task_id_branch__`, the dot-connected
root-to-node ID path. A context-task lifecycle log appends its own ID, but its
shared task Frame continues to expose the owning task-node branch.

`FailureCoveringContextTask` is the standard template for recovery contexts.
Subclasses implement `acquire`, `handle_exception`, and optionally `release`.
Successful handling and cleanup suppress the ordinary exception and mark the
context `FAILURE_COVERED`. Covered failures remain visible and still stop later
siblings; covering means the failure was wrapped up, not that execution can be
resumed safely.

## Execution and results

### Omitting child tasks

During its action, a task may call synchronous `context.skip_children()` to
omit all its children and their descendants, including their context tasks.
No status nodes (not even `SKIPPED`), lifecycle logs, or argument/output entries
are created for that subtree. The call is idempotent and irreversible for this
execution; it does not return early from the action or change its status.
Normal output validation/publication still occurs, entered contexts unwind in
reverse order, and successful completion permits later parent-level siblings.

The omission takes effect immediately, even if the action subsequently fails,
output publication fails, cleanup fails, or an exception is covered. Those
failures retain their normal reporting and propagation, but omitted children
are never added back as skipped status nodes. Cancellation still propagates.
Calls before or after the action's active lifetime raise `RuntimeError`;
context entry and exit are outside that lifetime. A task with no children may
call the method without additional effects. Each execution owns fresh control
state, including concurrent executions of the same workflow.

Static `to_lines()` still shows the complete definition tree, and CLI parameter
inference and required-input checks still consider all declared tasks.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

import lclang
import lclang.workflow as wf


@dataclass
class Options:
    run_children: bool


async def choose(
    context: wf.TaskContext,
    args: Options,
    status_mgr: wf.ExecutionStatusManager,
) -> Options:
    if not args.run_children:
        context.skip_children()
    return args


async def main() -> None:
    child = wf.define_task(
        "child", "Optional child", task_action=choose, args_mapping=Options(True),
    )
    root = wf.define_task(
        "root", "Choose children", task_action=choose,
        args_mapping=Options(False), children=[child],
    )
    async with lclang.define_frame() as frame:
        result = await wf.define_workflow("Conditional work", root).execute(
            wf.WorkflowExecutionContext(
                False, date(2026, 9, 21), False, logging.getLogger("skip-example"), frame,
            )
        )
    assert result.execution_status.status is wf.ExecutionStatus.SUCCESS
    assert result.execution_status.sub_tasks[0].sub_tasks == []
    assert set(result.task_args) == {"root"}
    assert result.task_outputs == {"root": Options(False)}


asyncio.run(main())
```

The root action chooses not to enter its child, then returns its normal output.
The root succeeds and retains that output; the child has no status node or
materialized values. The immutable definition still contains the child for
other executions that choose to run it.

### Result values

`await workflow.execute(context)` returns `WorkflowExecutionResult` with the
finalized `execution_status`, the borrowed `execution_frame`, and dictionaries
of successfully materialized action arguments and returned outputs. A key is
added to `task_args` after argument construction and to `task_outputs` after a
valid action return. Structural, unreached, and failed stages are absent.

Raised exceptions become `WorkflowException` under the shared Frame name
`__exception__`. The value retains the ordinary exception and originating
task or context-task ID. Explicit `FAILURE`, `ERROR`, or `FAILURE_COVERED`
statuses also stop execution and receive a deterministic synthetic exception.
All unexecuted declared branches appear as `SKIPPED`.

Severity is `ERROR`, `FAILURE`, `FAILURE_COVERED`, then `PENDING`. Clean work
retains the existing success/all-skipped aggregation rules. Process-control
`BaseException` values unwind task contexts and Frames, then propagate.

## Static trees and CLI conversion

`workflow.to_lines()` renders the definition without executing it. Task and
context lines show IDs, titles, argument flows (`field <- $variable`), output
flows (`field -> $variable`), literals, defaults, and unmapped fields. Context
entry lines nest above child tasks and matching exit lines appear below them in
reverse order.

`workflow.to_cli(name, summary, preset=None)` infers external variables by the
same scope-aware traversal. A context output is visible to later contexts, the owning action,
and all descendant tasks; an action output is visible globally after that
action. Variables first read without a visible assignment become CLI parameters:
they are optional with a variable default, applicable field defaults, or values from
workflow `lcl_mixin`, explicit `to_cli(preset=...)`, or the CLI entrance.
Explicit presets override workflow host defaults, which override entrance bindings;
variable defaults are below all of those sources.
an explicit `None` is a default too. Reading before a later assignment still
requires an input. Variables assigned before their first read, and write-only
variables, are omitted and cannot be directly overridden. Context assignments
do not hide inputs needed outside the owning subtree. Missing descriptions render as
`NO HELP MESSAGE PROVIDED`. Help groups parameters by scope and shows optional
defaults without loading configuration; see [parameter help](cli.md#parameter-help).

The generated command logs lifecycle records around every reached task and
context task. `task start` is INFO and appends ` (dryrun)` in dry-run mode. An
exception produces one `task error` record with the original traceback, then
finalization still produces `task complete`. Branches use the injected
dot-connected path. Completion severity follows the task status.

Verbose mode adds one aligned, sorted `args mapping` DEBUG record after
materialization and one `outputs mapping` record after completion when an output
exists. Runtime types remain visible for masked values. Sources and targets are
labelled as LCL variables, defaults, literals, or unused outputs.

The finalized workflow tree is one severity-aware multi-line record headed
`workflow complete: [command.path] STATUS:` and includes the existing tree root.
Exit codes are success `0`, failure `1`, error `2`, and covered failure `3`.

`lclang.cli.scan_commands(module, name, description)` imports a package and its
submodules deterministically, collects public module-level `Command` objects,
deduplicates re-exports by identity, and rejects distinct duplicate names.

### Context scope migration and cleanup failures

Ancestor context resources now shadow same-named external values in descendant
tasks. Outside sibling branches keep their own lookup environment. Ordinary
action outputs still publish to the shared workflow Frame. A context publishes
its acquisition-time resource, not a result only determined during exit.

Context exit remains reverse ordered after the whole owned subtree finishes.
An ordinary business exception and cleanup exceptions are retained together in
an exception group. Cancellation remains cancellation, with cleanup failures
attached as its cause; cleanup continues through the remaining outer contexts
and task Frames.

### Business event logs

`TaskContext.log_event(event, *, level=logging.INFO, record=None, fields=(),
masked_fields=(), **values)` emits an application event through the execution
logger and its existing configuration. Messages include a bounded event name,
the task branch, and dry-run status. Record metadata also supplies
`lclang_event`, `lclang_task_branch`, and `lclang_dryrun`.

`record` is an optional dataclass instance. Only direct fields explicitly named
in `fields` are selected, in declaration order of that selection; additional
values follow in keyword order. Unknown fields, repeated selections, or names
shared by the selection and keyword values raise `ValueError`. A non-dataclass
record raises `TypeError`. No dictionary indexing, methods, or implicit whole
record expansion occurs.

Disabled levels return before inspecting records or formatting values. Explicit
`masked_fields` are checked before reading selected fields or calling repr;
ordinary Python values do not acquire masks by object identity. Unmasked values
use `safe_repr` with its default 200-character limit. Standard and lclang loggers
attribute the call to the application's `log_event` line.
