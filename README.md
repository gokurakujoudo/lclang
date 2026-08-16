# lclang

LCL stands for **Lazy Context Language**. **Lazy** means that a definition is
evaluated only when a result needs it. **Context** means that reusable
definitions receive their concrete host inputs, lookup hierarchy, cache, and
lifecycle inside a short-lived `Frame`. **Language** means those definitions are
explicit expressions parsed and interpreted by lclang rather than ad hoc
substitution rules hidden in application code.

Use it when configuration is more than static data but should remain explicit,
inspectable, and separate from application code—for example, derived service
settings, deployment policy, command defaults, or request-scoped calculations.


## Why use LCL?

LCL is useful when configuration describes relationships between values, not
only values stored in a file. The questions below identify the problems its
Module-and-Frame model is designed to solve.

`lclang` is pure Python, requires Python 3.14 or newer, has no third-party
runtime dependencies, and is distributed under the MIT license.

### Are derived settings duplicated across environments?

Static data works well until several fields must agree. Copying a host name,
URL, or policy result into every environment creates multiple values that can
drift apart. LCL keeps the relationship itself in configuration:

```lclcfg
__LCL_VERSION__: 1

scheme: "https"
host: f"api.{environment}.example.com"
endpoint: f"{scheme}://{host}"
```

The application supplies `environment` for the current run. `host` and
`endpoint` remain derived definitions, so changing the input or the relationship
does not require synchronizing copied results. File-backed definitions also
retain source origins for diagnostics.

### Do the same rules need different inputs for each request or command?

Putting all configuration logic in Python can mix stable policy with transient
request data. LCL separates them: an immutable `Module` records what can be
calculated, while each `Frame` supplies what those definitions mean for one
run.

```python
import lclang


PRICING = lclang.define_module(
    "pricing",
    {
        "subtotal": "unit_price * quantity",
        "discount": "discount_for(customer_id, subtotal)",
        "total": "subtotal - discount",
    },
)


async def price_order(unit_price, quantity, customer_id, discount_for):
    async with lclang.define_frame(
        PRICING,
        preset={
            "unit_price": unit_price,
            "quantity": quantity,
            "customer_id": customer_id,
            "discount_for": discount_for,
        },
    ) as frame:
        return await frame.get("total")
```

`PRICING` can be parsed once and reused. Every call creates an independent
context with fresh inputs, result snapshots, dependency observations, and owned
asynchronous work. The supplied `discount_for` callable may be synchronous or
asynchronous; lclang awaits its result when necessary.

### Are optional or expensive values calculated even when nobody uses them?

Eager configuration generation can perform unnecessary work or fail because of
an unused branch. A Frame starts from the requested name and evaluates only the
definitions needed to produce it. In the pricing example,
`frame.get("subtotal")` does not call `discount_for`; `frame.get("total")` does.

The first lookup stores a value or ordinary failure as a snapshot. Concurrent
callers in the same event loop share the in-flight calculation, and later reads
receive the same result. Recalculation is explicit and never silently
invalidates dependants, making one Frame a predictable record of one run rather
than a reactive spreadsheet.

### Can you explain where a computed value came from?

Once configuration contains expressions, debugging only the final value is not
enough. LCL can inspect a definition without evaluating it:

```python
tree = frame.inspect_variable("total")
print("\n".join(tree.to_lines()))
```

The inspection tree reports definition owners, lookup paths, cache states,
dependencies, typed values, and failures. Source-aware errors carry the
variable evaluation stack, while static graphs and runtime dependency snapshots
support ordering and change-impact analysis. This keeps computed configuration
explicit even when it becomes more capable than a static data file.

### Is LCL the wrong tool for this configuration?

Use JSON, TOML, YAML, or plain Python data when the input is already static and
has no meaningful derived relationships. LCL is also not a hostile-code
sandbox: expressions, host values, and host callables must come from trusted
application configuration. Its purpose is to make trusted, contextual
calculation lazy and inspectable, not to execute untrusted user programs.


## Installation

```console
python -m pip install lclang
```

## The mental model

Most applications need only two concepts:

- A `Module` is an immutable set of named, unevaluated definitions. It answers:
  **what can be calculated?**
- A `Frame` combines a Module with host inputs, a lookup hierarchy, lazy result
  snapshots, and owned asynchronous work. It answers: **what do those
  definitions mean for this run?**

```text
          parse once                              create per run

  expression source ──> Module       Module + host inputs ──> Frame
                         │                                      │
                  reusable definitions                 lazy value snapshots
```

Modules are safe to reuse across requests, tenants, commands, and tests because
they contain no evaluation state. Frames are intentionally stateful and belong
to one event loop. Create a fresh Frame for each independent run and close it
when that run finishes.

This separation is the central lclang usage pattern: **define once, evaluate in
a short-lived context**.

## Preferred application pattern

Define the Module when the application loads. Supply narrow Python values when
creating the Frame, request the outputs you need, and use `async with` to close
the Frame deterministically.

```python
import asyncio

import lclang


INVOICE = lclang.define_module(
    "invoice",
    {
        "subtotal": "unit_price * quantity",
        "total": "subtotal + tax",
        "label": 'f"Total: {total:.2f}"',
    },
)


async def price_invoice(*, unit_price: float, quantity: int, tax: float) -> str:
    async with lclang.define_frame(
        INVOICE,
        preset={
            "unit_price": unit_price,
            "quantity": quantity,
            "tax": tax,
        },
    ) as frame:
        return await frame.get("label")


async def main() -> None:
    label = await price_invoice(unit_price=6.5, quantity=4, tax=2.0)
    assert label == "Total: 28.00"


asyncio.run(main())
```

Definition order is not evaluation order. Here `total` may refer to `subtotal`
regardless of where either appears in the mapping. Parsing validates every
expression up front; evaluation follows name lookups only when `frame.get()` is
called.

`define_module()` and `define_frame()` are the preferred high-level APIs. A
Frame created this way also receives lclang's reviewed pure builtins and the
`iter`, `text`, `data`, and `json` namespaces.

## Choose the smallest entry point

| Need | Preferred API | Ownership model |
| --- | --- | --- |
| Evaluate one expression in synchronous code | `evaluate_sync(source, values)` | lclang owns the temporary event loop |
| Evaluate related named definitions | `define_module()` + `async with define_frame()` | reuse the Module; the context manager closes each Frame |
| Load a `.lclcfg` file and read one value | `load_config()` + `evaluate_config()` | `evaluate_config()` closes its temporary Frame |
| Evaluate one parsed expression asynchronously | `parse_expression()` + `await evaluate()` | caller supplies the resolver values |
| Parse, print, or analyze syntax without running it | `parse_expression()` + `to_source()` or runtime analysis APIs | no evaluation state is created |
| Create many runs with the same policy | `FrameFactory` or `Config.frame_factory()` | use each created Frame as an async context manager |

For a small synchronous script, keep things direct:

```python
import lclang

total = lclang.evaluate_sync(
    "unit_price * quantity",
    {"unit_price": 6, "quantity": 4},
)
assert total == 24
```

Do not call `evaluate_sync()` from a running event loop. Async applications
should use Frames or await `evaluate()`.

## Values are snapshots, not reactive cells

The first `await frame.get("name")` evaluates the selected definition and caches
either its value or its ordinary failure. Concurrent callers in the same event
loop share that work. Later reads return the same snapshot.

For an optional direct lookup, pass `fallback=value`. The fallback is returned
unchanged only when the requested name is absent from the complete Frame
hierarchy; it is not cached. Omitting it, or passing `lclang.NO_FALLBACK`, keeps
the normal `LclNameError`. Existing definitions that fail still raise their
evaluation error, so `fallback=None` does not hide a broken definition.

```python
region = await frame.get("region", fallback="global")
```

Changing a host input does not automatically invalidate cached definitions or
their dependants. This is deliberate: recalculation is explicit and local.

```python
frame.mixin({"unit_price": 10})
await frame.recalculate("subtotal")
await frame.recalculate("total")
```

Think of a Frame as one reproducible calculation run, not as a spreadsheet. If
many inputs change together, creating a new Frame is often clearer than
refreshing an existing one. Use `mixin()` and `recalculate()` when retaining the
run's other snapshots is intentional.

## Configuration files are Modules with provenance

Use `.lclcfg` when definitions should live outside Python, be composed from
multiple files, or retain file and line information in diagnostics.

```lclcfg
__LCL_VERSION__: 1

scheme: "https"
host: f"api.{environment}.example.com"
endpoint: f"{scheme}://{host}"
```

Load files asynchronously. Use `evaluate_config()` when you need one result and
do not need to retain a Frame:

```python
from pathlib import Path

from lclang.config import evaluate_config, load_config


async def endpoint_for(environment: str) -> str:
    config = await load_config(Path("settings.lclcfg"))
    result = await evaluate_config(
        config,
        "endpoint",
        values={"environment": environment},
    )
    assert isinstance(result, str)
    return result
```

If several values must share one cache, convert the loaded configuration into a
Module or use `config.frame_factory()`, then use each created Frame in an
`async with` scope. `using` declarations expand other configuration sources in
source order; later definitions win while origin and history remain available
for diagnostics.

## Keep the Python boundary narrow

Names resolve through the user Module, supplied application values, runtime
values, reviewed builtins, and standard namespaces. Prefer passing plain values
or purpose-built callables rather than exposing broad service objects.

Host callables may be synchronous or asynchronous. lclang awaits resolver
values, call results, iterator operations, and context-manager protocols when
needed. Application code remains responsible for the behavior and authority of
anything it provides.

The language is expression-only and intentionally familiar:

```lcl
profile?.display_name ?? "anonymous"
[item * 2 for item in values if item > 0]
f"{service}: {port}"
value -> value * 2
(left, right=10) -> left + right
try primary() except ServiceError: fallback()
```

Arrow functions use `() -> expression`, `name -> expression`, or
`(parameters) -> expression`. Definitions are immutable syntax; lexical
closures retain the definition context in which they were created.

## Diagnostics and inspection

Expected library failures derive from `lclang.LclError`. Syntax, name,
evaluation, circular-dependency, closed-Frame, and configuration failures have
specific subclasses and retain source information where available.

Use `frame.has()` and `frame.get_definition()` for lookup checks that must not
evaluate anything. Use `frame.inspect_variable()` when debugging a value's
owner, cache state, dependency tree, or failure path. Dependency graphs and
snapshots are available when an application needs ordering or change-impact
analysis; they are not required for normal evaluation.

## Practical rules

1. Parse definitions once and reuse the resulting Module.
2. Create one Frame per independent run or request.
3. Pass only the host values that configuration actually needs.
4. Treat cached results as snapshots; recalculate explicitly.
5. Use every owned Frame as an async context manager so it closes on block exit.
6. Prefer `evaluate_config()` when reading only one configuration value.
7. Catch `LclError` at the application boundary and preserve its source-aware
   diagnostic text.

## Project resources

- [Documentation](https://jihulab.com/midnightprotocol/lclang/-/tree/main/docs)
- [Source](https://jihulab.com/midnightprotocol/lclang)
- [Issue tracker](https://jihulab.com/midnightprotocol/lclang/-/work_items)

## Requirements and license

- Python 3.14 or newer
- No third-party runtime dependencies
- MIT license
