# Runtime API guide

## Import layers

The package root exposes the preferred `define_module`/`define_frame` workflow,
the canonical `LCL_ROOT`, `LCL_BUILTINS`, `LCL_RUNTIME`, and `LCL_IMPORTS`
Frames, and the lower-level `Module`, `Frame`, `FrameFactory`, `Preset`,
`EvaluationLimits`, `DependencySnapshot`, and `STANDARD_PRESET` APIs.

Use `pylcl.runtime` for advanced static graph construction, topological order,
dynamic tracing, reconciliation values, and standard runtime types. Use
`pylcl.stdlib` for manifests, namespace assembly, individual reviewed helpers,
`STANDARD_MANIFESTS`, and `STANDARD_PRESET`.

## Direct expression evaluation

`pylcl.evaluate_sync(source, resolver=None)` is the preferred synchronous
one-expression boundary: string source is parsed with `parse_expression` and
then evaluated on a private event loop. It also accepts an already parsed AST
for tools that need to reuse syntax. It rejects calls made inside a running
event loop. Async code should parse explicitly and await `pylcl.evaluate`.

## Preferred definitions and canonical hierarchy

`define_module(name, exprs)` parses a string-to-string dictionary into an
immutable `Module`. `define_frame(module=None, base=LCL_RUNTIME, preset=None)`
creates a fresh user Frame. Lookup proceeds from the nearest layer through:

`user module -> LCL_IMPORTS -> LCL_RUNTIME -> LCL_BUILTINS -> LCL_ROOT`.

`LCL_ROOT` owns definition-scoped `lhs()` and the reviewed LCL namespaces.
`LCL_BUILTINS` owns curated ambient-I/O-free Python types/functions, including
strict `parse_ymd`/`to_ymd` date conversion and the variadic eager fixed-point
helper `recursive`; `LCL_RUNTIME` is the empty package default and may be
replaced with one CLI-aware base per run; `LCL_IMPORTS` is the detached preset
layer. User definitions therefore win over presets, which win over runtime
values. Canonical ancestors are borrowed and closing a user Frame never closes
them.

The fixed builtin inventory is: value types `bool`, `bytes`, `dict`, `float`,
`frozenset`, `int`, `list`, `set`, `str`, and `tuple`; functions `abs`, `all`,
`any`, `bin`, `chr`, `divmod`, `enumerate`, `filter`, `format`, `hex`,
`isinstance`, `len`, `map`, `max`, `min`, `oct`, `ord`, `parse_ymd`, `pow`,
`range`, `recursive`, `repr`, `reversed`, `round`, `slice`, `sorted`, `sum`,
`to_ymd`, and `zip`. File/process input,
dynamic import/code, reflection, and mutation helpers are deliberately absent.

`recursive(builder)` returns a callable eager fixed point. Its representation is
`Recursive Function: <original source>`: an LCL function builder uses canonical
LCL source, while a Python builder uses its function name. Frame inspection
uses this representation directly and never includes a Python object address.

## Explicit Module, Preset, and FrameFactory

`Module` copies a name-to-AST mapping into a read-only snapshot. `Preset` does
the same for host bindings; `overlay` is shallow and right-biased. A
`FrameFactory` retains a Module, optional Preset, and optional default
`EvaluationLimits`. Each `create` call has fresh cache, task, dependency, and
lifecycle state. Call-level values and limits override factory policy. Parent
Frames are borrowed, not owned. `create()` and direct `Frame(module)` both
default their ID to `frame-<module name>`; an ordinary non-empty string or
`FrameId` overrides that diagnostic default.

Prefer `parent.derive(module, values={})` for an ordinary child Frame. It copies
local host values, uses the module name as the child ID, owns fresh cache/task/
dependency/lifecycle state, and borrows `parent`. Use direct `Frame`
construction when child-specific limits or values are required.

## Frame caching and concurrency

`await frame.get(name)` lazily evaluates a local definition once, caching either
its result or ordinary failure. Concurrent callers in one event loop share one
owner task. Waiter cancellation is isolated. Circular dependency paths raise a
structured error before an owner can deadlock. Parent definitions always run in
their defining Frame.

Structured errors raised while evaluating Frame definitions expose
`variable_stack`, an immutable direct-to-failing owner tuple. Their one-line
text appends the same route, for example
`[variable evaluation stack: RESULT -> intermediate -> failing]`. Lazy child
definitions and LCL closure calls add their lexical owner; propagation and
cached failures retain the first, deepest stack. Errors created by direct
expression evaluation outside a Frame have an empty stack.

All synchronous and asynchronous iterable items pass through the recursive
auto-await boundary before comprehensions, starred expansion, or reviewed
`iter.collect`/`iter.first` helpers consume them. In particular,
`[*map(def (x): x.lower(), ["A", "B"])]` evaluates to `["a", "b"]` without
retaining coroutine objects.

`frame.has(name)` checks whether that same recursive lookup selects either a
definition or host value. `frame.get_definition(name)` returns the selected
custom AST without evaluation, or `None` when the name is missing or a nearer
host value masks an ancestor definition. Both methods preserve all cache,
dependency, task, and lifecycle state.

`frame.inspect_variable(name)` returns a `VariableInspectionTree` whose direct
children are unique by first-seen variable name. Each node exposes its status (`Cached`,
`NotEvaluated`, `ExternalProvided`, or `NativeProvided`), selected AST, exact lookup path, owning
Frame, current value or exception, and static dependency children. Missing
names remain diagnostic leaves and cycles stop only on the repeating branch;
the same name can still appear independently beneath separate parent branches.
Inspection never evaluates or awaits anything, joins work, changes caches, or
publishes traces. `repr(tree)` is a compact
`name@frame/path: [definition ](Status) typed-payload` line using canonical LCL
source. External and native values omit definition text, unresolved names use
`<missing>`, ordinary values use `type: repr`, and errors use
`ErrorType: message`.
When a current value is a supported `LclAstNode`, its typed payload uses
canonical LCL source instead of the Python dataclass repr, for example
`LclBinary: base + 2`. Evaluated LCL closures similarly render as
`LclFunctionValue: def (...): ...`, without exposing their bound parameters,
resolver, evaluator, source spans, or other implementation state. This applies
equally to external host values and cached definition results, without
evaluating the represented value.
Canonical reviewed values in `LCL_ROOT` and `LCL_BUILTINS` are
`NativeProvided`; every callable uses `Builtin Function: <binding-name>` and
every reviewed namespace uses `Builtin Namespace: <namespace-name>`.
Application, preset, and CLI host values remain `ExternalProvided` and retain
their ordinary typed reprs.
`tree.to_lines()` returns a markdown-style nested list of those lines.

`frame.mixin(values)` atomically copies a right-biased dictionary into the open
Frame's host bindings. The existing `frame.values` view remains read-only while
reflecting the update. Direct lookups and uncached definitions see mixed values;
already cached definition successes/failures remain snapshots. Call
`recalculate` explicitly when a definition should observe a new mixed input.
Module definitions continue to shadow same-name host values.

`await frame.recalculate(name)` atomically replaces only the named definition's
snapshot; it never invalidates a dependant. Old values remain readable during
refresh. Ordinary success/failure replaces value/failure and dependency trace;
owner cancellation preserves the prior snapshots.

## Dependency snapshots

`frame.dependency_snapshot(name)` is synchronous point-in-time inspection. It
returns static edges, observed dynamic edges, and confirmed/inactive/unexpected
reconciliation. Before evaluation all static edges are inactive. Cached reads
do not add observations. Deferred function/generator lookups extend their
defining source's published trace. Parent lookups route to the owner.

`pylcl.runtime.build_dependency_graph(frame)` performs a separate static,
non-evaluating hierarchy analysis. It returns `FrameDependencyGraph` with
qualified `FrameDependencyBinding` definitions/value terminals and
`FrameDependencyEdge` occurrences. Each edge contains `lookup_path`, its
requested `target_name`, and the selected binding or `None`. Module input keeps
returning the original unqualified `DependencyGraph`.

See the [dependency analytics tutorial](../tutorials/dependency-analytics.md)
for the complete static-to-runtime methodology and executable examples.

## Limits and close

`EvaluationLimits` caps semantic AST depth, node visits, and one materialized
collection. One root evaluation chain shares its task-local budget; cached reads
consume none and recalculate starts fresh.

`await frame.close()` rejects new work, cancels and settles owned tasks, and
cleans cached resources once in reverse acquisition order. It recognizes sync
`close` and async `aclose`. Parent resources remain parent-owned. Cleanup errors
are stable, and cancelling a waiter does not cancel shared close work.

## Standard preset and errors

`STANDARD_PRESET` exposes pure-data `iter`, `text`, `data`, and `json`
namespaces. It has no file, environment, network, subprocess, reflection, or
dynamic-import helpers. Individual helpers validate their input protocols and
their failures become source-aware structured evaluation failures at the
interpreter boundary.

LCL is for trusted application configuration. It is not a security sandbox for
hostile expressions. Values and callables supplied by the host can execute
ordinary Python behaviour, including blocking or side effects, so applications
must review their own Presets.
