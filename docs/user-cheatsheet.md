# pylcl Python user cheatsheet

This is the practical Python-side reference for every public feature implemented
in pylcl 0.1. Use it when embedding LCL in an application, testing expressions,
building lazy runtime modules, inspecting dependencies, or supplying reviewed
host functions.

For the language itself, read the [complete LCL V1 syntax guide](lcl-lang.md).
For a shorter first run, use the
[runtime quickstart](tutorials/runtime-quickstart.md). The
[runtime API guide](reference/runtime-api.md) explains the runtime contracts in
more narrative form. The [project ledger](../progress.md) is authoritative about
implemented versus planned releases.

> Current scope: expression parsing/evaluation and the runtime/standard-library
> APIs are implemented. `.lclcfg` files and the CLI are planned for later
> releases; no Python API for either is advertised here. Package metadata remains
> `0.0.0` until the 0.1 artifact gate, and `pylcl.__version__` reports that value.

## Choose the right API layer

| Import | Use it for |
|---|---|
| `import pylcl` | Normal application work: parse, print, evaluate, build Modules/Frames, apply limits, inspect snapshots, and use `STANDARD_PRESET`. |
| `import pylcl.lang` | Lexer tokens plus the parse/print/evaluate front end. |
| `import pylcl.ast` | Complete immutable AST families, structural walking, visitors, and manual AST construction. |
| `import pylcl.runtime` | Static dependency analysis/graphs, ordering, dynamic tracing, reconciliation, and the runtime value types. |
| `import pylcl.stdlib` | Individual reviewed helpers and custom manifest/namespace assembly. |

The root package intentionally stays focused. Advanced graph and standard-library
construction names are not root attributes. All evaluation is async-first;
`evaluate_sync` is the one synchronous convenience boundary.

## Parse, inspect, print, and evaluate LCL

### Parse a complete expression

`parse_expression(text, *, origin=None, version=LCL_V1)` returns an immutable
custom `LclAstNode`. It consumes the entire input and raises `LclSyntaxError` for
empty, malformed, or trailing source. `LanguageVersion` currently contains
`LanguageVersion.V1`; `LCL_V1` is its convenient stable alias.

Use nominal string wrappers to make application identifiers explicit:
`SourceName`, `ModuleName`, `FrameId`, and `VarName`. They are typing aids and
behave like strings at runtime.

<!-- pylcl-exec -->
```python
import pylcl
from pylcl.lang import TokenKind, scan_tokens

origin = pylcl.SourceOrigin(pylcl.SourceName("settings:price"))
node = pylcl.parse_expression(
    "price * quantity",
    origin=origin,
    version=pylcl.LCL_V1,
)

assert pylcl.to_source(node) == "price * quantity"
assert pylcl.evaluate_sync(node, {"price": 6, "quantity": 7}) == 42
assert node.span.origin is origin

tokens = scan_tokens("total ?? 0", origin=origin)
assert [token.kind for token in tokens] == [
    TokenKind.IDENTIFIER,
    TokenKind.DOUBLE_QUESTION,
    TokenKind.INTEGER,
    TokenKind.EOF,
]
assert tokens[2].value == 0
```

### Scan tokens when tooling needs lexical detail

`pylcl.lang.scan_tokens(text, *, origin=None)` returns a list ending in exactly
one `TokenKind.EOF`. Each `Token` contains `kind`, exact `lexeme`, source `span`,
and a decoded `value` for literals. Offsets and columns count Unicode code
points, not encoded bytes. Most applications should parse directly; token
scanning is useful for editors, diagnostics, and source tools.

### Inspect or construct the immutable AST

Every node is an `LclAstNode` with a half-open `span`. Use `children()` for direct
children, `walk()` for preorder traversal including the root, and `accept()` with
an `LclVisitor` when an application owns a visitor abstraction.

```python
import pylcl
from pylcl.ast import LclName

tree = pylcl.parse_expression("subtotal + tax")
names = [node.name for node in tree.walk() if isinstance(node, LclName)]
assert names == ["subtotal", "tax"]


class ClassNameVisitor:
    def visit(self, node: pylcl.LclAstNode) -> str:
        return type(node).__name__


assert tree.accept(ClassNameVisitor()) == "LclBinary"
```

Manual construction is supported through `pylcl.ast`, but parsing is normally
less verbose and supplies accurate spans. Source-less manual nodes use an empty
unknown span. The public families are:

- atoms: `LclConstant`, `LclName`, `LclTuple`;
- operations: `LclUnary`, `LclBinary`, `LclBoolean`, `LclCompare`,
  `LclConditional`, `LclCoalesce`;
- primaries: `LclAttribute`, `LclSafeAttribute`, `LclSlice`, `LclSubscript`,
  `LclCall`;
- call arguments: `LclPositionalArgument`, `LclStarArgument`,
  `LclKeywordArgument`, `LclKeywordUnpackArgument`;
- displays: `LclStarred`, `LclList`, `LclSet`, `LclKeyValue`, `LclDictUnpack`,
  `LclDict`;
- comprehensions: `LclComprehensionClause`, `LclGenerator`,
  `LclListComprehension`, `LclSetComprehension`, `LclDictComprehension`;
- formatted strings: `LclStringText`, `LclFormattedValue`, `LclJoinedString`;
- functions and failures: `ParameterKind`, `LclParameter`, `LclFunction`,
  `LclRaise`, `LclAssert`;
- control forms: `LclExceptHandler`, `LclTry`, `LclWithItem`, `LclWith`.

Operator enums are implementation-facing today and are reached through their
node fields; canonical source should be obtained with `to_source(node)` rather
than assembling text from enum values. `to_source` preserves semantics and
operator precedence, but formatting/comments and original quote choices are not
round-tripped.

### Evaluate directly

`await evaluate(node, resolver=None)` accepts either a string-keyed mapping or an
object with `async resolve(name, *, span)`. Results from names, operations,
calls, iterators, context managers, and container children are automatically
awaited. Direct evaluation has no Frame cache or Frame resource limits.

```python
import asyncio

import pylcl


async def main() -> None:
    node = pylcl.parse_expression("base + extra")
    assert await pylcl.evaluate(node, {"base": 40, "extra": 2}) == 42


asyncio.run(main())
```

Synchronous code may call `evaluate_sync(node, resolver)`. It creates a private
event loop and fails with `RuntimeError` when the current thread already has a
running loop: `evaluate_sync cannot run` there, so async callers must await
`evaluate`.

## Build Modules, Presets, factories, and Frames

### Module

`Module(ModuleName(...), definitions)` snapshots a mapping of non-empty names to
parsed AST values. The mapping is read-only after construction. A Module is a
definition template; it contains no cache, task, or evaluated value.

```python
module = pylcl.Module(
    pylcl.ModuleName("billing"),
    {
        "subtotal": pylcl.parse_expression("unit_price * quantity"),
        "total": pylcl.parse_expression("subtotal + tax"),
    },
)
```

### Preset and call-level host values

`Preset(name, values)` snapshots reusable host bindings. Values themselves are
retained by reference. `left.overlay(right, name=...)` is shallow and
right-biased. `FrameFactory.with_preset(preset)` returns a new factory whose new
preset wins over collisions in the old one.

When a Frame resolves a name, precedence is:

1. a local Module definition;
2. call-level/factory host values;
3. the parent Frame.

`FrameFactory.create(..., values=...)` applies the factory Preset first and then
overlays call-level values. A Module definition still shadows both.

### FrameFactory and Frame

`FrameFactory(module, preset=None, limits=None)` is reusable immutable policy.
Every `create(frame_id, *, values=None, parent=None, limits=None)` returns a
fresh independent `Frame`; call-level limits replace factory defaults. Parents
are borrowed, not owned.

Construct `Frame(module, frame_id, *, values=None, parent=None, limits=None)`
directly when a reusable factory adds no value.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.Module(
        pylcl.ModuleName("billing"),
        {
            "subtotal": pylcl.parse_expression("unit_price * quantity"),
            "total": pylcl.parse_expression("subtotal + tax"),
        },
    )
    host = pylcl.Preset("billing-host", {"unit_price": 6, "tax": 2})
    limits = pylcl.EvaluationLimits(
        max_depth=100,
        max_steps=10_000,
        max_collection_items=1_000,
    )
    factory = pylcl.FrameFactory(module, host, limits)
    frame = factory.create(
        pylcl.FrameId("request:42"),
        values={"quantity": 5},
    )
    try:
        assert await frame.get("total") == 32
        assert await frame.get("total") == 32  # cached snapshot
        assert frame.module is module
        assert frame.frame_id == "request:42"
        assert frame.closed is False
    finally:
        await frame.close()
    assert frame.closed is True


asyncio.run(main())
```

### Parent Frames

A child falls back to `parent` only after its local definitions and values.
Parent definitions always evaluate/cache/recalculate in the parent that defines
them. Closing a child never closes the borrowed parent.

```python
parent = pylcl.Frame(parent_module, pylcl.FrameId("parent"), values={"region": "eu"})
child = pylcl.Frame(child_module, pylcl.FrameId("child"), parent=parent)
try:
    value = await child.get("value")
finally:
    await child.close()
    await parent.close()
```

## Cache, concurrency, recalculation, and cleanup

### Lazy result and failure snapshots

`await frame.get(name)` evaluates a local definition on first access. Successful
values and ordinary exception instances are cached. Later reads return/raise the
same snapshot. Host binding values are resolved and auto-awaited but are not
definition-cache entries.

Concurrent callers in one event loop share one owner task per name. Cancelling a
waiter does not cancel the owner or other waiters. A Frame must not be shared
across event loops.

### Explicit recalculation

`await frame.recalculate(name)` evaluates a definition again and atomically
publishes the new success/failure and dependency trace. Ordinary readers keep
seeing the previous snapshot until commit. Owner cancellation leaves the prior
snapshot intact. Recalculation never invalidates dependants: refresh those names
explicitly in application-selected order. Host bindings cannot be recalculated.

```python
old_value = await frame.get("subtotal")
new_value = await frame.recalculate("subtotal")
# A previously cached "total" is unchanged until explicitly recalculated.
```

### Evaluation limits

`EvaluationLimits(max_depth=100, max_steps=100_000,
max_collection_items=10_000)` requires positive non-boolean integers. One root
Frame evaluation chain shares a task-local budget. Cached reads cost nothing;
each recalculation starts a fresh budget. A collection limit applies to each
materialized collection, not to lazy generators.

### Close every Frame

Always `await frame.close()` in `finally`. Close rejects new work, cancels and
settles owned tasks, and closes cached resources once in reverse acquisition
order. A cached resource may expose sync `close()` or async `aclose()`. Cancelling
one close waiter does not cancel shared cleanup. `closed` becomes true only after
cleanup settles. Cleanup errors are `LclEvaluationError`; parent resources stay
parent-owned.

## Analyze and observe dependencies

Dependencies preserve individual source occurrences. `DependencyKind` values are
`EAGER`, `CONDITIONAL`, `DEFERRED`, and runtime-only `DYNAMIC`.

### Static analysis

`analyze_dependencies(node)` returns ordered `DependencyReference` values with
`name`, `kind`, and exact `span`. It understands lexical bindings, conditional
branches, short-circuiting, comprehensions, functions, try, and with forms.

`build_dependency_graph(module)` produces an immutable `DependencyGraph` whose
`definitions` retain declaration order and whose `edges` are `DependencyEdge`
occurrences (`source`, `target`, `kind`, `span`). Use:

- `graph.dependencies(source, kinds=None)` for outgoing occurrences;
- `graph.dependants(target, kinds=None)` for incoming occurrences;
- `graph.external_names` for unique non-local targets in first-use order;
- `topological_order(graph, kinds=...)` for deterministic dependency-first local
  ordering. It defaults to eager edges and raises `LclCircularDependencyError`
  when the selected local subgraph cycles.

<!-- pylcl-exec -->
```python
import pylcl
from pylcl.runtime import (
    DependencyKind,
    analyze_dependencies,
    build_dependency_graph,
    topological_order,
)

module = pylcl.Module(
    pylcl.ModuleName("graph"),
    {
        "base": pylcl.parse_expression("host"),
        "total": pylcl.parse_expression("base + tax"),
    },
)
references = analyze_dependencies(module.definitions["total"])
assert [(str(ref.name), ref.kind) for ref in references] == [
    ("base", DependencyKind.EAGER),
    ("tax", DependencyKind.EAGER),
]

graph = build_dependency_graph(module)
assert [str(name) for name in graph.external_names] == ["host", "tax"]
assert [str(edge.target) for edge in graph.dependencies("total")] == ["base", "tax"]
assert [str(edge.source) for edge in graph.dependants("base")] == ["total"]
assert [str(name) for name in topological_order(graph)] == ["base", "total"]
```

### Dynamic observation and reconciliation

`DependencyTrace(source)` records actual name/span occurrences. Wrap an existing
async resolver with `TracingResolver(trace, parent)` and evaluate through the
wrapper; `trace.edges` is an immutable point-in-time tuple of dynamic edges.
Repeating the exact target/span is idempotent.

`reconcile_dependency_edges(static_edges, dynamic_edges)` returns a
`DependencyReconciliation` with `confirmed`, `inactive`, and `unexpected`
partitions. Static inputs must not contain `DYNAMIC`; dynamic inputs must contain
only `DYNAMIC`.

Frames do this integration for you. `frame.dependency_snapshot(name)` returns a
`DependencySnapshot` containing the static edges, observed dynamic edges, and
their reconciliation. Before evaluation, predicted edges are inactive. Cached
reads do not create new observations. Closures and generators may extend the
defining source's published trace when later used.

```python
snapshot = frame.dependency_snapshot("total")
for edge in snapshot.reconciliation.confirmed:
    print(edge.source, "->", edge.target, edge.kind, edge.span)
```

## Use and extend the standard preset

### Built-in reviewed namespaces

`STANDARD_PRESET` is assembled from `STANDARD_MANIFESTS` in stable order. It
provides read-only attribute/mapping namespaces and no ambient filesystem,
environment, network, subprocess, reflection, or import helpers.

| LCL spelling | Direct Python helper | Behaviour |
|---|---|---|
| `iter.collect(values)` | `collect(values)` | Async: collect a sync or async iterable into a fresh list. |
| `iter.first(values, default)` | `first(values, default=None)` | Async: return the first item without consuming later items, or the default. |
| `text.join(separator, values)` | `join(separator, values)` | Async: join only string items from sync/async iteration. |
| `text.lines(value, keep_ends=false)` | `lines(value, keep_ends=False)` | Split Unicode text with `str.splitlines` semantics. |
| `data.merge(*mappings)` | `merge(*mappings)` | Shallow left-to-right merge returned as a read-only mapping. |
| `data.lookup(mapping, key, default)` | `lookup(mapping, key, default=None)` | Return present value or explicit default; present `None` is preserved. |
| `json.encode(value)` | `json_encode(value)` | Compact, Unicode-friendly strict JSON; rejects NaN/infinity. |
| `json.decode(text)` | `json_decode(text)` | Strict JSON to ordinary Python scalars/lists/dicts. |

Each helper is independently importable from `pylcl.stdlib`. LCL automatically
awaits the async helpers.

### Assemble an application-specific reviewed library

`StdlibEntry(name, value, summary)` describes one opaque reviewed export.
`StdlibManifest(namespace, entries)` creates an ordered root namespace.
`assemble_stdlib(manifests, name="stdlib")` returns a `Preset` of
`StdlibNamespace` values. Names must be public identifiers, may not be keywords,
underscore-prefixed, or collide with reserved mapping/metadata members. Duplicate
entries or root namespaces fail early. Assembly never calls or awaits values.

`StdlibNamespace` is a read-only `Mapping[str, object]`: use either
`namespace["member"]` or `namespace.member` in Python, while LCL naturally uses
attribute access.

<!-- pylcl-exec -->
```python
import asyncio

from pylcl.stdlib import (
    StdlibEntry,
    StdlibManifest,
    assemble_stdlib,
    collect,
    first,
    join,
    json_decode,
    json_encode,
    lines,
    lookup,
    merge,
)


async def numbers():
    yield 1
    yield 2


async def main() -> None:
    assert await collect(numbers()) == [1, 2]
    assert await first([], "empty") == "empty"
    assert await join("-", ["a", "b"]) == "a-b"
    assert lines("a\nb") == ["a", "b"]
    assert dict(merge({"a": 1}, {"a": 2, "b": 3})) == {"a": 2, "b": 3}
    assert lookup({"present": None}, "present", 9) is None
    assert json_encode({"answer": 42}) == '{"answer":42}'
    assert json_decode('[true, null]') == [True, None]

    manifest = StdlibManifest(
        "mathx",
        [StdlibEntry("double", lambda value: value * 2, "Double one value.")],
    )
    preset = assemble_stdlib([manifest], name="application-stdlib")
    namespace = preset.values["mathx"]
    assert namespace["double"](21) == 42
    assert namespace.double(5) == 10


asyncio.run(main())
```

To add reviewed host capabilities alongside the standard set, overlay Presets:

```python
application = pylcl.Preset("application", {"clock": clock_function})
factory = pylcl.FrameFactory(module, pylcl.STANDARD_PRESET).with_preset(application)
```

## Source locations and errors

### Source values

`SourceOrigin(SourceName(...), path=None)` gives diagnostics a display name and
optional `pathlib.Path`. `SourcePosition(line, column, offset)` uses one-based
line/column and zero-based Unicode-code-point offset. `SourceSpan(origin, start,
end)` is half-open and rejects a backwards offset range. Parsed tokens and AST
nodes carry these values automatically.

```python
from pathlib import Path

import pylcl

origin = pylcl.SourceOrigin(
    pylcl.SourceName("app settings"),
    Path("settings.lcl"),
)
try:
    pylcl.parse_expression("1 +", origin=origin)
except pylcl.LclSyntaxError as error:
    assert error.span is not None
    assert error.span.origin is origin
    assert error.code == "LCL1001"
```

### Structured exception hierarchy

Catch the narrowest useful type. Every `LclError` has `message`, stable `code`,
and optional `span`; `str(error)` includes source name/line/column when present.

| Exception | Meaning / default code |
|---|---|
| `LclError` | Base expected library failure, `LCL0001`. |
| `LclSyntaxError` | Invalid LCL source, `LCL1001`. |
| `LclNameError` | Unresolved evaluator/Frame/graph name, `LCL2001`. |
| `LclEvaluationError` | Evaluation, host protocol, limit, or cleanup failure, `LCL3001`. |
| `LclCircularDependencyError` | Runtime or selected graph cycle, `LCL3002`. |
| `LclClosedFrameError` | Work requested after close starts, `LCL3003`. |
| `LclConfigError` | Reserved public base for the later config API, `LCL4001`. |
| `LclCliError` | Reserved public base for the later CLI API, `LCL5001`. |
| `LclCliUsageError` | Reserved CLI-usage subtype, `LCL5002`. |

Ordinary host `Exception` values are wrapped once as `LclEvaluationError` and
retained as the cause. Existing LCL errors pass through. Direct `BaseException`
values such as cancellation, `KeyboardInterrupt`, and `SystemExit` propagate
after required cleanup rather than being wrapped as configuration failures.

## Complete public symbol inventory

This inventory is intentionally exhaustive and is checked against each module's
current `__all__`. Use the earlier sections for behaviour and examples.

### `pylcl`

- Language/version: `LCL_V1`, `LanguageVersion`, `__version__`,
  `parse_expression`, `to_source`, `evaluate`, `evaluate_sync`.
- Nominal/source values: `FrameId`, `ModuleName`, `SourceName`, `VarName`,
  `SourceOrigin`, `SourcePosition`, `SourceSpan`.
- Root AST values: `LclAstNode`, `LclConstant`, `LclName`, `LclTuple`,
  `LclVisitor`.
- Runtime: `Module`, `Preset`, `FrameFactory`, `Frame`, `EvaluationLimits`,
  `DependencySnapshot`, `STANDARD_PRESET`.
- Errors: `LclError`, `LclSyntaxError`, `LclNameError`, `LclEvaluationError`,
  `LclCircularDependencyError`, `LclClosedFrameError`, `LclConfigError`,
  `LclCliError`, `LclCliUsageError`.

### `pylcl.lang`

`Token`, `TokenKind`, `scan_tokens`, `parse_expression`, `to_source`, `evaluate`,
and `evaluate_sync`.

### `pylcl.runtime`

`Module`, `Preset`, `FrameFactory`, `Frame`, `EvaluationLimits`,
`DependencyKind`, `DependencyReference`, `DependencyEdge`, `DependencyGraph`,
`DependencyTrace`, `TracingResolver`, `DependencyReconciliation`,
`DependencySnapshot`, `analyze_dependencies`, `build_dependency_graph`,
`topological_order`, and `reconcile_dependency_edges`.

### `pylcl.stdlib`

`STANDARD_MANIFESTS`, `STANDARD_PRESET`, `StdlibEntry`, `StdlibManifest`,
`StdlibNamespace`, `assemble_stdlib`, `collect`, `first`, `join`, `lines`,
`merge`, `lookup`, `json_encode`, and `json_decode`.

### `pylcl.ast`

`LclAstNode`, `LclVisitor`, `LclConstant`, `LclName`, `LclTuple`, `LclUnary`,
`LclBinary`, `LclBoolean`, `LclCompare`, `LclConditional`, `LclCoalesce`,
`LclAttribute`, `LclSafeAttribute`, `LclSlice`, `LclSubscript`, `LclCall`,
`LclPositionalArgument`, `LclStarArgument`, `LclKeywordArgument`,
`LclKeywordUnpackArgument`, `LclStarred`, `LclList`, `LclSet`, `LclKeyValue`,
`LclDictUnpack`, `LclDict`, `LclComprehensionClause`, `LclGenerator`,
`LclListComprehension`, `LclSetComprehension`, `LclDictComprehension`,
`LclStringText`, `LclFormattedValue`, `LclJoinedString`, `ParameterKind`,
`LclParameter`, `LclFunction`, `LclRaise`, `LclAssert`, `LclExceptHandler`,
`LclTry`, `LclWithItem`, and `LclWith`.

## Rainy cases and operational rules

- Treat LCL as trusted configuration, not a hostile-code sandbox. Host bindings
  can perform arbitrary Python side effects, block the event loop, or expose
  capabilities. Review Presets and resolvers.
- `parse_expression` parses one expression, not assignment/config files. It
  raises `LclSyntaxError` for malformed or trailing input and `ValueError` for an
  unsupported language version.
- `evaluate_sync cannot run` inside an active event loop. Use `await evaluate`.
- Unknown names raise `LclNameError`. Ordinary host failures become
  `LclEvaluationError` with their cause; do not discard the cause during logging.
- Local Module definitions shadow host values. A child Frame's local definitions
  and values shadow the parent. Call-level values override factory Preset values.
- A circular lookup raises `LclCircularDependencyError`; concurrent access does
  not turn a true cycle into a deadlock.
- A Frame is task-concurrent within one event loop, not cross-loop or cross-thread
  mutable state. Create independent Frames for independent loop ownership.
- Cached successes and failures are snapshots. Recalculation never invalidates
  dependants, and cancellation never commits a partial refresh.
- Always close Frames. A request after closing starts raises
  `LclClosedFrameError`; one cancelled close waiter does not cancel cleanup.
- `EvaluationLimits` constrain semantic work but are not security isolation,
  timeouts, memory accounting, or protection from blocking host code.
- Static dependency edges are predictions. Conditional/deferred edges may remain
  inactive; dynamic evidence records only lookups that actually occurred.
- `STANDARD_PRESET` deliberately has no ambient I/O. Add capabilities explicitly,
  narrowly, and preferably through reviewed manifests or Presets.
