# Dependency analytics

lclang can answer two different questions about a definition:

1. **What could this expression read?** Static analysis inspects immutable ASTs.
2. **What did this evaluation actually read?** Runtime tracing records successful
   and failed name lookups while a `Frame` evaluates.

Static analysis and graph construction do not evaluate an expression. Runtime
evidence appears only after you explicitly request a Frame value.

## Concepts

A dependency is one free-name occurrence. If `total` is `subtotal + tax`, the
expression has two occurrences: `total -> subtotal` and `total -> tax`.
Repeated occurrences remain separate because their source spans may matter to
diagnostics and reconciliation.

`DependencyKind` explains when an occurrence may run:

- `EAGER`: ordinary evaluation always reaches it.
- `CONDITIONAL`: a branch, short circuit, handler, or filter may skip it.
- `DEFERRED`: a function body or lazy generator may read it later.
- `DYNAMIC`: runtime tracing observed the lookup during an actual evaluation.

The main immutable results are:

- `DependencyReference`: one static free-name occurrence in an AST.
- `DependencyGraph`: definitions and static edges for a `Module`.
- `FrameDependencyGraph`: qualified definitions, host-value terminals, and
  lookup paths for a complete Frame hierarchy.
- `DependencySnapshot`: static and runtime evidence for one Frame definition.

## Methodology

Use the narrowest level that answers your question:

1. Parse one expression and call `analyze_dependencies` to explain its syntax.
2. Call `build_dependency_graph(module)` for definition-to-definition design
   analysis and topological ordering.
3. Call `build_dependency_graph(frame)` when parent lookup, shadowing, and host
   values affect where a name resolves.
4. Call `frame.inspect_variable(name)` for a readable, branch-preserving tree
   with unique direct names, owners, lookup paths, and current cache evidence.
5. Evaluate a value only when you need observed behavior, then inspect
   `frame.dependency_snapshot(name)`.
6. Use `reconcile_dependency_edges` directly when comparing evidence captured
   outside a Frame snapshot.

## Debug one variable without evaluation

A graph is best for whole-system queries such as dependants and ordering. A
`VariableInspectionTree` is better for explaining one result: it shows each
direct variable once per parent in first-seen order, follows parent ownership
exactly as evaluation would, and places cache/value/error evidence beside each
node. The same variable can still appear independently on separate branches.

<!-- lclang-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    parent = lclang.Frame(
        lclang.define_module("rates", {"tax": "subtotal * rate"}),
        "rates",
        values={"rate": 0.2},
    )
    child = lclang.Frame(
        lclang.define_module(
            "invoice",
            {
                "subtotal": "price * quantity",
                "total": "subtotal + tax + tax",
            },
        ),
        "invoice",
        values={"price": 10, "quantity": 3},
        parent=parent,
    )
    try:
        tree = child.inspect_variable("total")
        assert [str(item.var_name) for item in tree.dependencies] == ["subtotal", "tax"]
        first_tax = tree.dependencies[1]
        assert first_tax.definition_path == [
            lclang.FrameId("invoice"),
            lclang.FrameId("rates"),
        ]
        assert first_tax.defined_at is parent
        assert first_tax.dependencies[0].definition_path == [lclang.FrameId("rates")]
        assert tree.status.value == "NotEvaluated"
        assert child.dependency_snapshot("total").dynamic_edges == ()

        rendered = "\n".join(tree.to_lines())
        assert (
            "total@invoice: subtotal + tax + tax "
            "(NotEvaluated) NoneType: None"
        ) in rendered
        assert rendered.count("tax@invoice/rates:") == 1
    finally:
        await child.close()
        await parent.close()


asyncio.run(main())
```

Results: both direct `tax` occurrences collapse into one explanatory child,
which resolves through `invoice -> rates`. The parent-owned `tax` definition resolves its own
`subtotal` lookup starting at `rates`; the child definition does not leak into
the parent scope. Because `subtotal` is missing there, that child is a leaf with
`LclNameError` in `current_exception`. Nothing is evaluated, so the root is
still `NotEvaluated` and its runtime trace stays empty. This makes the tree a
safe first diagnostic before deciding whether an actual evaluation is useful.
Dependency graphs and snapshots remain occurrence-preserving when exact spans
or repeated uses matter; only the explanatory tree deduplicates direct names.

## Analyze one expression

```python
from lclang import parse_expression
from lclang.runtime import analyze_dependencies

node = parse_expression("cached if enabled else compute(input_value)")
references = analyze_dependencies(node)

result = [(str(item.name), item.kind.value) for item in references]
assert result == [
    ("enabled", "eager"),
    ("cached", "conditional"),
    ("compute", "conditional"),
    ("input_value", "conditional"),
]
```

Result: `enabled` is eager because the condition must run. Both alternatives
are conditional because only one branch is selected. Static analysis reports
possibilities; it does not call `compute`.

## Build a Module graph

```python
import lclang
from lclang.runtime import DependencyKind, build_dependency_graph, topological_order

module = lclang.define_module(
    "invoice",
    {
        "quantity": "2",
        "subtotal": "quantity * unit_price",
        "total": "subtotal * (1 + tax_rate)",
        "label": "() -> f'{total:.2f}'",
    },
)
graph = build_dependency_graph(module)

assert [str(edge.target) for edge in graph.dependencies("subtotal")] == [
    "quantity",
    "unit_price",
]
assert graph.external_names == ("unit_price", "tax_rate")
assert topological_order(graph) == ("quantity", "subtotal", "total", "label")
assert graph.dependencies("label")[0].kind is DependencyKind.DEFERRED
```

Results:

- `quantity`, `subtotal`, `total`, and `label` are local graph vertices.
- `unit_price` and `tax_rate` are external to the Module. A Module has no host
  values or parent Frame, so it cannot resolve them further.
- The default topological order considers eager edges. `label` can be placed
  without requiring `total` first because its function body is deferred.

Pass a kind set to `dependencies`, `dependants`, or `topological_order` when a
tool needs a different risk model. An empty set deliberately selects no edges.

## Resolve a Frame hierarchy without evaluation

A `FrameDependencyGraph` applies real Frame lookup rules: local definitions
before same-Frame values, then each parent in order. Bindings carry a
`frame_path`, while every edge records the exact `lookup_path` searched.

<!-- lclang-exec -->
```python
import asyncio

import lclang
from lclang.runtime import FrameDependencyGraph, build_dependency_graph


async def main() -> None:
    calls = 0

    def explode() -> int:
        nonlocal calls
        calls += 1
        return 99

    module = lclang.define_module(
        "invoice",
        {
            "quantity": "2",
            "subtotal": "quantity * unit_price",
            "danger": "explode()",
        },
    )
    frame = lclang.Frame(
        module,
        lclang.FrameId("request"),
        values={"unit_price": 3, "explode": explode},
    )
    try:
        graph = build_dependency_graph(frame)
        assert isinstance(graph, FrameDependencyGraph)
        subtotal = next(item for item in graph.definitions if item.name == "subtotal")
        edges = graph.dependencies(subtotal)
        assert [str(edge.target_name) for edge in edges] == ["quantity", "unit_price"]
        assert edges[0].target is not None
        assert edges[0].target.kind.value == "definition"
        assert edges[1].target is not None
        assert edges[1].target.kind.value == "value"
        assert calls == 0
        assert frame.dependency_snapshot("subtotal").dynamic_edges == ()

        assert await frame.get("subtotal") == 6
        snapshot = frame.dependency_snapshot("subtotal")
        assert [str(edge.target) for edge in snapshot.dynamic_edges] == [
            "quantity",
            "unit_price",
        ]
        assert len(snapshot.reconciliation.confirmed) == 2
        assert snapshot.reconciliation.inactive == ()
        assert snapshot.reconciliation.unexpected == ()
        assert calls == 0
    finally:
        await frame.close()


asyncio.run(main())
```

Before `frame.get`, graph construction found both definition and value targets,
but the cache and dynamic trace were empty and `explode` was untouched. After
the explicit `subtotal` evaluation, its two predicted occurrences were also
observed, so reconciliation classifies both as confirmed.

Host values are terminals: the graph records their names and qualified owners,
not the opaque Python objects themselves. This lets tooling inspect a Frame
without retaining secrets, invoking callables, awaiting values, or performing
I/O.

## Static versus runtime evidence

Consider `cached if enabled else remote()`:

- Static analysis marks `cached` and `remote` conditional.
- If `enabled` is true, runtime tracing confirms `enabled` and `cached`.
- The `remote` edge remains inactive; that does not mean it is invalid.
- A dynamic lookup with no matching static occurrence becomes unexpected.

`DependencySnapshot.reconciliation` performs this exact occurrence comparison,
including source spans. Recalculation publishes a fresh trace atomically; it
does not invalidate cached dependants.

## Common uses

- **Configuration review:** list external Module names that a host must supply.
- **Impact analysis:** call `dependants(target)` to find definitions that may
  consume a changed binding.
- **Evaluation planning:** use `topological_order` with selected kinds.
- **Debugging:** compare inactive predictions with confirmed runtime lookups.
- **UI and provenance tools:** display qualified Frame owners and search paths
  without evaluating trusted configuration during inspection.

## Important boundaries

- Graphs are immutable snapshots. Rebuild after changing Frame host values.
- Static analysis follows language scope rules but cannot predict arbitrary
  behavior inside opaque Python callables.
- A runtime snapshot describes the latest published evaluation of that
  definition, not every evaluation in the Frame's history.
- `build_dependency_graph(frame)` detects cyclic parent object graphs and fails
  instead of publishing ambiguous paths.
- Dependency analytics explains trusted configuration; it is not a security
  sandbox or a side-effect detector for host functions.
