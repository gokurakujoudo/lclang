# Runtime API guide

## Import layers

The package root exposes the preferred `define_module`/`define_frame` workflow,
the canonical `LCL_ROOT`, `LCL_BUILTINS`, `LCL_RUNTIME`, and `LCL_IMPORTS`
Frames, and the lower-level `Module`, `Frame`, `FrameFactory`, `Preset`,
`EvaluationLimits`, `DependencySnapshot`, `LclRecord`, `NO_FALLBACK`, and
`STANDARD_PRESET` APIs.

Use `lclang.runtime` for advanced static graph construction, topological order,
dynamic tracing, reconciliation values, and standard runtime types. Use
`lclang.stdlib` for manifests, namespace assembly, individual reviewed helpers,
`STANDARD_MANIFESTS`, and `STANDARD_PRESET`.

## Direct expression evaluation

`lclang.evaluate_sync(source, resolver=None)` is the preferred synchronous
one-expression boundary: string source is parsed with `parse_expression` and
then evaluated on a private event loop. It also accepts an already parsed AST
for tools that need to reuse syntax. It rejects calls made inside a running
event loop. Async code should parse explicitly and await `lclang.evaluate`.

`{a=expression, b=expression}` evaluates to `lclang.LclRecord`. LCL and Python
both read fields with ordinary attributes, such as `record.a`. The public
`LclRecord(fields)` constructor copies one non-empty mapping whose keys obey the
same identifier, reserved-word, and `__` restrictions as record syntax.
Records expose no mapping or subscription protocol. Assignment and deletion
fail, while nested values retain their original identity and mutability.
Equality and hashing compare field names and values without declaration order;
hashing fails normally when a field value is unhashable. `repr` retains
declaration order, for example `LclRecord(a=1, b=2)`.

## Preferred definitions and canonical hierarchy

`define_module(name, exprs)` parses a string-to-string dictionary into an
immutable `Module`. `define_frame(module=None, base=LCL_RUNTIME, preset=None)`
creates a fresh user Frame. Lookup proceeds from the nearest layer through:

`user module -> LCL_IMPORTS -> LCL_RUNTIME -> LCL_BUILTINS -> LCL_ROOT`.

`LCL_ROOT` owns definition-scoped `lhs()`. `LCL_BUILTINS` owns the reviewed
standard and calendar namespaces plus curated Python types/functions, including
strict `parse_ymd`/`to_ymd` date conversion and the variadic eager fixed-point
helper `recursive`; `LCL_RUNTIME` is the empty package default and may be
replaced with one CLI-aware base per run; `LCL_IMPORTS` is the detached preset
layer. User definitions therefore win over presets, which win over runtime
values. Canonical ancestors are borrowed and closing a user Frame never closes
them.

Definition and host-value names may be qualified paths such as
`service.database.port`. The runtime stores the complete spelling as one flat
binding. Missing prefixes are lazy `FrameProxy` views over the requesting
Frame; they create no nested Frames or separate caches. `FRAME_PROXY` may be
used as an optional complete binding value to document a prefix explicitly.
Real ancestor/descendant binding pairs are rejected eagerly.

Python may use `await frame.get("service.database.port")`, or obtain the root
proxy and use `await service.database.port`. String indexing is identical, so
`await service["database"].port` in Python and `service["database"].port` in LCL
retain the same lookup, tracing, caching, and errors. A non-string proxy index
raises `TypeError`; a missing attribute or index raises the same
`AttributeError`. References remain fully qualified: `service.total` and
`total` are separate.

`await proxy.get(name, default=None)` performs direct-child lookup and returns
the default only when that child is absent. `await proxy.field_names()` returns
the sorted, unique immediate effective child identifiers across the Frame
hierarchy, including inferred prefixes but excluding the proxy marker.
`await proxy.as_record(DataclassType)` resolves present initializer fields in
declaration order and constructs a detached dataclass instance. Absent fields
are omitted so dataclass defaults and default factories apply; extra children,
non-initializer fields, `ClassVar`, and `InitVar` do not participate. The type
must be a dataclass, missing required constructor values fail normally, and
child evaluation errors propagate.

`await frame.evaluate(expr)` parses and evaluates one unnamed LCL expression
against an open Frame. The expression itself is not cached or entered into a
dependency snapshot, although named definitions reached through it retain
their normal snapshots and flights. `lhs()` returns `"<expr>"` during this
evaluation and in closures it creates.

The fixed builtin inventory also includes the distinct `env` environment utility. `env.NAME`
reads the live process environment and returns `None` when absent;
`env.get("non-identifier", default)` supports arbitrary environment names.
Scoped definitions and values named `env.NAME` win, including explicit `None`,
without mutating `os.environ`. `env.NAME ?? default` is the ordinary LCL
fallback form, and `env.field_names()` includes valid current environment names
plus effective scoped overrides.

The remaining fixed builtin inventory is: value types `bool`, `bytes`, `dict`, `float`,
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

Anonymous LCL functions use `() -> expression`, `name -> expression`, or
`(parameters) -> expression`. The bare name is only a single required positional
parameter shorthand. Canonical source always parenthesizes the signature.

## Explicit Module, Preset, and FrameFactory

`Module` copies a name-to-AST mapping into a read-only snapshot. `Preset` does
the same for host bindings; `overlay` is shallow and right-biased. A single
trailing `!` on a binding key marks its normalized exact name as masked, so
`{"token!": value}` creates the runtime name `token`. Modules, Presets, Frames,
direct resolver mappings, Frame mixins, and CLI binding sources share this
spelling. Their immutable `masked_names` metadata retains the policy, and
`frame.is_masked(name)` checks it without evaluating the name. Once marked in
an effective Frame hierarchy, a same-name override stays masked; unrelated or
derived names do not inherit the flag. Direct `Frame(..., masked_names=...)` and
`frame.derive(..., masked_names=...)` calls may also overlay an exact inherited
name, which lets an application boundary redact a borrowed parent value without
copying it. Module and Preset trailing-`!` declarations still name bindings in
their own source. A
`FrameFactory` retains a Module, optional Preset, and optional default
`EvaluationLimits`. Each `create` call has fresh cache, task, dependency, and
lifecycle state. Call-level values and limits override factory policy. Parent
Frames are borrowed, not owned. `create()` and direct `Frame(module)` both
default their ID to `frame-<module name>`; an ordinary non-empty string or
`FrameId` overrides that diagnostic default.

Prefer `async with parent.derive(module, values={}) as child:` for an ordinary
owned child Frame. It copies local host values, uses the module name as the
child ID, owns fresh cache/task/dependency/lifecycle state, and borrows
`parent`. Leaving the child block closes only that child; the parent remains
open. Use direct `Frame` construction when child-specific limits or values are
required.

## Frame caching and concurrency

`await frame.get(name, fallback=NO_FALLBACK)` lazily evaluates a selected
definition once, caching either its result or ordinary failure. If *name* is
absent from the complete Frame hierarchy, an explicitly supplied fallback is
returned unchanged and is not cached. `None` is a valid fallback. The exported
`NO_FALLBACK` sentinel is the default and preserves the normal `LclNameError`.
Fallbacks do not replace failures raised while evaluating an existing
definition.

Concurrent callers in one event loop share one owner task. Waiter cancellation
is isolated. Circular dependency paths raise a structured error before an owner
can deadlock. Parent definitions always run in their defining Frame.

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
`[*map((x) -> x.lower(), ["A", "B"])]` evaluates to `["a", "b"]` without
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
`LclFunctionValue: (...) -> ...`, without exposing their bound parameters,
resolver, evaluator, source spans, or other implementation state. This applies
equally to external host values and cached definition results, without
evaluating the represented value.
Canonical reviewed values in `LCL_ROOT` and `LCL_BUILTINS` are
`NativeProvided`; every callable uses `Builtin Function: <binding-name>` and
every reviewed namespace uses `Builtin Namespace: <namespace-name>`.
Application, preset, and CLI host values remain `ExternalProvided` and retain
their ordinary typed reprs.
`tree.to_lines()` returns a markdown-style nested list of those lines.
For a masked node, `repr(tree)` replaces definition, value, and failure payloads
with `*masked*`; `to_lines()` also omits that node's descendants. The detached
tree still exposes its raw fields to trusted Python callers, so masking is
diagnostic redaction rather than access control.

`frame.mixin(values)` atomically copies a right-biased dictionary into the open
Frame's host bindings. The existing `frame.values` view remains read-only while
reflecting the update. Direct lookups and uncached definitions see mixed values;
already cached definition successes/failures remain snapshots. Call
`recalculate` explicitly when a definition should observe a new mixed input.
Module definitions continue to shadow same-name host values.

Mixin validation includes every open descendant that borrows the updated
Frame. A conflicting update is rejected before any value changes.

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

`lclang.runtime.build_dependency_graph(frame)` performs a separate static,
non-evaluating hierarchy analysis. It returns `FrameDependencyGraph` with
qualified `FrameDependencyBinding` definitions/value terminals and
`FrameDependencyEdge` occurrences. Each edge contains `lookup_path`, its
requested `target_name`, and the selected binding or `None`. Module input keeps
returning the original unqualified `DependencyGraph`.

See the [dependency analysis tutorial](../tutorials/08-dependency-analysis.md)
for the progressive static-to-runtime workflow and expected results.

## Limits and close

`EvaluationLimits` caps semantic AST depth, node visits, and one materialized
collection. One root evaluation chain shares its task-local budget; cached reads
consume none and recalculate starts fresh.

Frames implement the asynchronous context-manager protocol. Prefer
`async with lclang.define_frame(...) as frame:` so leaving the block always
awaits owned cleanup. The context manager returns the same Frame and never
suppresses an exception raised by the block.

`await frame.close()` is the lower-level explicit equivalent. It rejects new
work, cancels and settles owned tasks, and cleans cached resources once in
reverse acquisition order. It recognizes sync `close` and async `aclose`.
Parent resources remain parent-owned. Cleanup errors are stable, and cancelling
a waiter does not cancel shared close work.

## Standard preset and errors

`STANDARD_PRESET` independently exposes pure-data `iter`, `text`, `data`, and
`json` namespaces. Canonical Frames merge them into `LCL_BUILTINS`. The preset
has no file, environment, network, subprocess, reflection, or
dynamic-import helpers. Individual helpers validate their input protocols and
their failures become source-aware structured evaluation failures at the
interpreter boundary.

LCL is for trusted application configuration. It is not a security sandbox for
hostile expressions. Values and callables supplied by the host can execute
ordinary Python behaviour, including blocking or side effects, so applications
must review their own Presets.
