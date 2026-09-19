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

Create variables through the subscribed factory:

```python
import lclang.workflow as wf

source = wf.define_variable[int]("source", "Required source value")
secret = wf.define_variable[str]("service.token", "Service token", is_masked=True)
result = wf.define_variable[float]("result")
```

`TaskVar.quote` is statically typed as the represented value but returns the
variable marker at runtime. It can therefore occupy a normally typed dataclass
field in a definition mapping. Argument fields containing a marker are resolved
from the current task Frame. Other fields retain their literal value, including
values supplied by dataclass defaults.

Output publication is opt-in. With no output mapping, nothing is published.
Within a mapping, only fields containing `TaskVar.quote` are copied from the
returned dataclass into a Frame; other fields are retained in `task_outputs`
but remain unmapped. Masked variables use the same exact-name redaction model
as Modules, Presets, configuration, CLI bindings, and Frame mixins.

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
children. Their mapped resources enter only the current task Frame. Every task
Frame is derived directly from the shared execution Frame, so a context resource
never leaks to another task. Mapped action outputs enter the shared Frame and
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
same scope-aware traversal. A context output is visible only to later contexts
and the action in its task; an action output is visible globally after that
action. Variables first read without a visible assignment become required CLI
parameters. Intermediate variables are omitted and cannot be directly
overridden. Missing descriptions render as `NO HELP MESSAGE PROVIDED`.

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
