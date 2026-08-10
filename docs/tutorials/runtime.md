# Runtime: Modules and Frames

The pylcl runtime turns expression source into values while keeping parsing,
host inputs, evaluation, and lifecycle ownership explicit. This guide starts
with the two concepts used by almost every application: **Module** and **Frame**.

## The mental model

A `Module` is an immutable, unevaluated mapping from names to LCL syntax trees.
It answers “what can be calculated?” A `Frame` combines one Module with host
values, an optional parent, a lazy result cache, and owned asynchronous work. It
answers “what does this name mean for this run?”

```text
Module (definitions only) + host values + optional parent
                         |
                         v
                  Frame (one run)
                         |
             lazy values and failure snapshots
```

Modules are reusable and have no evaluation state. Frames are intentionally
stateful: each Frame has independent snapshots and belongs to one event loop.

## Evaluate one expression synchronously

For a small synchronous script, pass source text directly to `evaluate_sync`:

<!-- pylcl-exec -->
```python
import pylcl

assert pylcl.evaluate_sync("unit_price * quantity", {"unit_price": 6, "quantity": 4}) == 24
```

This is the preferred synchronous convenience. Use `parse_expression` first
only when you also need the immutable AST for printing or dependency analysis.
Async applications should use Modules and Frames, or await `evaluate` with an
already parsed AST; `evaluate_sync` deliberately rejects a running event loop.

## Define and evaluate a Module

`define_module(name, expressions)` is the normal construction API. The keys are
definition names and the values are complete LCL expressions.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module(
        "invoice",
        {
            "total": "subtotal + tax",
            "subtotal": "unit_price * quantity",
            "label": 'f"Total: {total:.2f}"',
        },
    )
    frame = pylcl.define_frame(
        module,
        preset={"unit_price": 6.5, "quantity": 4, "tax": 2.0},
    )
    try:
        assert await frame.get("subtotal") == 26.0
        assert await frame.get("total") == 28.0
        assert await frame.get("label") == "Total: 28.00"
    finally:
        await frame.close()


asyncio.run(main())
```

Definition order does not control dependency order: `total` can appear before
`subtotal`. Parsing builds syntax trees; the Frame follows name lookups only
when a value is requested.

## Lazy snapshots, not reactive cells

The first `await frame.get("name")` evaluates that definition. Concurrent
callers in the same event loop share one owner task. The successful value—or an
ordinary failure—is then cached. Later reads return the same snapshot.

This is deliberately not a spreadsheet-style reactive system. Updating a host
value or recalculating one definition never invalidates its dependants. You
choose which snapshots to refresh and in what order.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module(
        "mutable-inputs",
        {
            "subtotal": "unit_price * quantity",
            "total": "subtotal + tax",
        },
    )
    frame = pylcl.define_frame(
        module,
        preset={"unit_price": 6, "quantity": 5, "tax": 2},
    )
    try:
        assert await frame.get("total") == 32
        frame.mixin({"unit_price": 10})

        assert await frame.recalculate("subtotal") == 50
        assert await frame.get("total") == 32  # still the old snapshot
        assert await frame.recalculate("total") == 52
    finally:
        await frame.close()


asyncio.run(main())
```

`frame.mixin()` is a right-biased update to local host values. Module
definitions still shadow same-name host values. `frame.values` is a read-only
live view of those host values; evaluated definition results are separate.

Use `frame.has(name)` and `frame.get_definition(name)` to inspect lookup without
triggering evaluation. The latter returns the selected custom AST, or `None` if
no definition is selected.

### Inspect one variable as a tree

`frame.inspect_variable(name)` is the most direct debugging view when you want
to understand both lookup and dependency structure. It returns the selected
definition, its owning Frame and lookup path, current cache state, current value
or exception, and one child for each first-seen direct dependency name. It does not
evaluate a definition, call or await a host value, join in-flight work, or add a
runtime dependency trace.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module(
        "invoice-debug",
        {
            "total": "subtotal + tax",
            "subtotal": "unit_price * quantity",
        },
    )
    frame = pylcl.Frame(
        module,
        values={"unit_price": 6, "quantity": 4, "tax": 2},
    )
    try:
        tree = frame.inspect_variable("total")
        assert tree.status.value == "NotEvaluated"
        assert tree.definition_path == [pylcl.FrameId("frame-invoice-debug")]
        assert [str(item.var_name) for item in tree.dependencies] == ["subtotal", "tax"]
        assert tree.dependencies[1].status.value == "ExternalProvided"
        assert tree.dependencies[1].current_value == 2
        assert frame.dependency_snapshot("total").dynamic_edges == ()

        lines = tree.to_lines()
        assert lines[0] == (
            "- total@frame-invoice-debug: subtotal + tax "
            "(NotEvaluated) NoneType: None"
        )
        assert lines[1] == (
            "  - subtotal@frame-invoice-debug: "
            "unit_price * quantity (NotEvaluated) NoneType: None"
        )
    finally:
        await frame.close()


asyncio.run(main())
```

`repr(tree)` is deliberately one line in
`name@frame/path: [definition ](Status) typed-payload` form, while
`tree.to_lines()` produces a markdown-style nested list suitable for logs,
issue reports, or a notebook. Definitions use canonical LCL source followed by
one space. External leaves omit definition text; missing leaves display
`<missing>`. Values use `type: repr`, and errors use `ErrorType: message`.
An `LclAstNode` stored as a host or cached value is the source-oriented
exception to ordinary Python repr: inspection prints its concrete type followed
by canonical LCL expression text. For example, a host value created with
`parse_expression("base+2")` renders as:

```text
expression@frame-app: (ExternalProvided) LclBinary: base + 2
```

The original AST object remains in `current_value`; inspection only changes its
display and performs no evaluation. Evaluated LCL functions use the same
source-oriented style:

```text
quicksort@frame-app: definition (Cached) LclFunctionValue: def (items): ...
```

The closure keeps working normally, while its representation hides bound
parameter, resolver, evaluator, and source-span implementation details.
Values produced by the native `recursive` builtin similarly use
`Recursive Function: <original source>`; LCL builders retain canonical source
and Python builders use their function name.
`Cached` means a definition has a committed value or failure snapshot;
`NotEvaluated` means it does not; `ExternalProvided` means lookup selected an
application host value; `NativeProvided` means it selected a reviewed canonical
pylcl builtin or namespace. Missing references remain visible as `NotEvaluated` leaves with an
`LclNameError` in `current_exception`. Repeated direct names collapse, cycles
end at the repeated node on that branch, and the same variable reached through
different branches remains as separate children.

## Where names come from

The preferred `define_frame` helper builds this lookup chain:

```text
user Module -> imports/preset -> runtime -> builtins -> standard namespaces
```

The nearest definition or host value wins. pylcl's reviewed defaults include
ordinary pure helpers such as `len`, `range`, `sorted`, and `sum`, plus the
`iter`, `text`, `data`, and `json` namespaces. They deliberately exclude file,
network, process, environment, reflection, and dynamic-import capabilities.
Inspection renders all reviewed functions and namespaces with one uniform,
implementation-independent grammar:

```text
len@frame-app/LCL_BUILTINS: (NativeProvided) Builtin Function: len
iter@frame-app/LCL_BUILTINS/LCL_ROOT: (NativeProvided) Builtin Namespace: iter
```

Two compact calendar helpers live in the builtin layer. `parse_ymd(text)`
strictly parses eight ASCII `YYYYMMDD` digits into `datetime.date`, while
`to_ymd(date)` formats a date with a four-digit year. They use no locale,
timezone, clock, or ambient state.

The root layer also provides `lhs()`. During `name: expression` evaluation it
returns `"name"`, which is useful for self-describing values:

```python
module = pylcl.define_module("named", {"k": '{"name": lhs()}'})
frame = pylcl.define_frame(module)
try:
    assert await frame.get("k") == {"name": "k"}
finally:
    await frame.close()
```

`lhs()` is definition context, not general reflection. Direct
`evaluate(parse_expression("lhs()"))` has no left-hand name and fails. Nested
definition evaluation receives the nested owner's name; task-local context
keeps concurrent definitions isolated.

The same task-local ownership produces actionable evaluation errors. If
`RESULT` depends on `subtotal`, whose expression fails, the structured error has
`variable_stack == ("RESULT", "subtotal")` and its text ends with
`[variable evaluation stack: RESULT -> subtotal]`. Calls through an LCL function
include that function's lexical definition owner. The deepest route is retained
when the same failure propagates or is returned from the Frame failure cache.

Supply application values narrowly:

```python
frame = pylcl.define_frame(
    module,
    preset={
        "region": "eu-west",
        "feature_flags": {"new_checkout": True},
    },
)
```

Host callables may be synchronous or asynchronous. LCL automatically awaits
resolver values, call results, iterator operations, and context-manager
protocols when they are awaitable.

## Independent Frames and factories

Reuse one Module across requests, tenants, or tests by creating a new Frame for
each run. A `FrameFactory` packages a Module, optional `Preset`, and default
`EvaluationLimits`; every `create` call still receives fresh cache and lifecycle
state.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module("price", {"total": "price * quantity"})
    factory = pylcl.FrameFactory(module)
    retail = factory.create(values={"price": 8, "quantity": 2})
    wholesale = factory.create(
        pylcl.FrameId("wholesale"),
        values={"price": 5, "quantity": 20},
    )
    try:
        assert retail.frame_id == pylcl.FrameId("frame-price")
        assert await retail.get("total") == 16
        assert await wholesale.get("total") == 100
    finally:
        await retail.close()
        await wholesale.close()


asyncio.run(main())
```

Direct `Frame(module)`, `FrameFactory.create()`, and their string-ID forms all
normalize an omitted identifier to `frame-<module name>`. Supplying a
`FrameId` remains useful for static typing but is not required.

Lower-level factories do not automatically add the canonical standard
hierarchy; their definitions must be satisfied by factory values, call values,
or an explicit parent. Use `define_frame` when you want the normal application
defaults. Provide an explicit ID when several Frames need distinct diagnostic
identities.

## Parent and child Frames

A child Frame falls back to its parent after local definitions and values. Use
`parent.derive(child_module, values={...})` for normal child construction.
Parent definitions always evaluate and cache in the Frame that owns them.
Closing a child does not close its borrowed parent.

```python
parent_module = pylcl.define_module("environment", {"region": '"eu"'})
child_module = pylcl.define_module("service", {"endpoint": 'f"api.{region}"'})
parent = pylcl.define_frame(parent_module)
child = parent.derive(child_module)
try:
    endpoint = await child.get("endpoint")
finally:
    await child.close()
    await parent.close()
```

## Inspect dependencies

Before evaluation, `frame.dependency_snapshot(name)` contains static predictions.
After evaluation it also contains the actual dynamic name lookups. The
reconciliation separates confirmed, inactive, and unexpected edges.

```python
snapshot = frame.dependency_snapshot("total")
for edge in snapshot.dynamic_edges:
    print(f"{edge.source} -> {edge.target}")
```

For whole-Module analysis, `pylcl.runtime.build_dependency_graph(module)` is
pure and does not evaluate anything. Passing a Frame instead returns a
`FrameDependencyGraph`: definitions and host-value terminals carry qualified
Frame paths, and every edge records the exact owner lookup path plus the
selected binding (or `None` when unresolved). Parent-owned definitions begin
their dependency lookup at their parent owner, exactly as evaluation would.
Graph construction never calls a value, resolves an awaitable, fills a cache,
or changes a dynamic trace.

Advanced graph queries and topological ordering are described in the
[dependency analytics tutorial](dependency-analytics.md) and
[runtime API guide](../reference/runtime-api.md).

## Limits and errors

`EvaluationLimits` can cap AST depth, evaluation steps, and items in one
materialized collection. Limits are operational guardrails, not a security
sandbox or a timeout for blocking host code.

Expected library failures derive from `pylcl.LclError`:

- `LclSyntaxError` — invalid expression source;
- `LclNameError` — no definition or host value resolves a name;
- `LclEvaluationError` — an operation, host protocol, assertion, limit, or
  cleanup failed;
- `LclCircularDependencyError` — Frame lookup found a dependency cycle;
- `LclClosedFrameError` — work was requested after closing began.

Errors retain source spans where possible. Ordinary host exceptions are wrapped
once and remain available as `error.__cause__`.

## Always close owned Frames

Use `try/finally` around every Frame you create. `await frame.close()` rejects
new work, cancels and settles owned tasks, and closes cached resources once in
reverse acquisition order. A parent is borrowed; close it separately only when
your code owns it.

Next, explore the [LCL examples gallery](lcl_examples.md), or load a complete
[configuration file](config_file.md).
