# Dependency analysis

lclang can answer two different questions: what an expression *could* read, and
what one evaluation *did* read. Static analysis works from immutable syntax;
dynamic tracing records actual successful and failed Frame lookups.

## What you will learn

- how eager, conditional, and deferred references differ;
- how to build and query a Module dependency graph;
- how runtime snapshots reconcile predictions with observations;
- which analysis level fits review, ordering, impact, or debugging.

## Analyze one expression without running it

Conditional branches remain possible dependencies even though only one branch
runs for a particular input.

<!-- lclang-doc-exec -->
```python
import lclang
from lclang.runtime import analyze_dependencies

node = lclang.parse_expression(
    "cached if enabled else compute(input_value)"
)
references = analyze_dependencies(node)
result = [(str(item.name), item.kind.value) for item in references]

assert result == [
    ("enabled", "eager"),
    ("cached", "conditional"),
    ("compute", "conditional"),
    ("input_value", "conditional"),
]
```

The condition must always read `enabled`, making it eager. `cached` belongs
only to the true branch, while both `compute` and its argument belong only to
the false branch. Static analysis consequently marks all three branch-local
occurrences conditional without choosing a branch.

A name inside an arrow-function body is deferred because creating the function
does not run its body. Repeated references remain separate occurrences so their
source spans and reconciliation evidence are not lost.

## Build and query a Module graph

Graph vertices are local definitions. Names not defined by the Module are
reported as external requirements.

<!-- lclang-doc-exec -->
```python
import lclang
from lclang.runtime import build_dependency_graph, topological_order

module = lclang.define_module(
    "invoice",
    {
        "quantity": "2",
        "subtotal": "quantity * unit_price",
        "total": "subtotal * (1 + tax_rate)",
        "label": '() -> f"{total:.2f}"',
    },
)
graph = build_dependency_graph(module)

assert [str(edge.target) for edge in graph.dependencies("subtotal")] == [
    "quantity",
    "unit_price",
]
assert tuple(str(name) for name in graph.external_names) == (
    "unit_price",
    "tax_rate",
)
assert topological_order(graph) == ("quantity", "label", "subtotal", "total")
```

`subtotal` points to local `quantity` and external `unit_price`; `total` adds
the external `tax_rate`. Those are the only names absent from the Module.
Eager ordering can place `label` early because its reference to `total` is
inside a deferred function body, then orders `subtotal` before `total`.

The default topological order uses eager edges. Because `label` contains a
deferred function body, it can appear before `subtotal` and `total`.

## Reconcile static and runtime evidence

This final example evaluates the true branch. The remote dependency remains a
valid static possibility but is classified as inactive for this run.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    calls = 0

    def remote() -> int:
        nonlocal calls
        calls += 1
        return 99

    module = lclang.define_module(
        "choice",
        {"result": "cached if enabled else remote()"},
    )
    async with lclang.define_frame(
        module,
        preset={"cached": 42, "enabled": True, "remote": remote},
    ) as frame:
        assert await frame.get("result") == 42
        snapshot = frame.dependency_snapshot("result")
        assert [str(edge.target) for edge in snapshot.dynamic_edges] == [
            "enabled",
            "cached",
        ]
        assert [str(edge.target) for edge in snapshot.reconciliation.inactive] == [
            "remote",
        ]
        assert calls == 0


asyncio.run(main())
```

At runtime, `enabled` resolves true, so evaluation reads `cached` and returns
`42`. It never traverses the false branch, leaving the statically predicted
`remote` occurrence inactive. The empty call count independently confirms that
reconciliation did not execute the skipped host function.

Use `build_dependency_graph(frame)` when parent lookup, shadowing, and host
value terminals matter. Graph construction remains non-evaluating. Rebuild a
Frame graph after changing host bindings because it is an immutable snapshot.

[Previous: Errors and inspection](07-errors-and-inspection.md) | [Next: Command-line applications](09-command-line-applications.md) | [Return to the series introduction](README.md)
