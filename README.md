# lclang

`lclang` is a small, async-first configuration language for Python applications.
It lets you describe related values as expressions, provide environment-specific
inputs from Python, and evaluate only the values a particular run needs.

Use it when configuration is more than static data but should remain explicit,
inspectable, and separate from application code—for example, derived service
settings, deployment policy, command defaults, or request-scoped calculations.

`lclang` is pure Python, requires Python 3.14 or newer, has no third-party
runtime dependencies, and is distributed under the MIT license.

> LCL is intended for trusted application configuration. It is not a sandbox
> for expressions supplied by an attacker. Values and callables provided by the
> host application retain their ordinary Python capabilities.

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
creating the Frame, request the outputs you need, and close the Frame in a
`finally` block.

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
    frame = lclang.define_frame(
        INVOICE,
        preset={
            "unit_price": unit_price,
            "quantity": quantity,
            "tax": tax,
        },
    )
    try:
        return await frame.get("label")
    finally:
        await frame.close()


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
| Evaluate related named definitions | `define_module()` + `define_frame()` | reuse the Module; close each Frame |
| Load a `.lclcfg` file and read one value | `load_config()` + `evaluate_config()` | `evaluate_config()` closes its temporary Frame |
| Evaluate one parsed expression asynchronously | `parse_expression()` + `await evaluate()` | caller supplies the resolver values |
| Parse, print, or analyze syntax without running it | `parse_expression()` + `to_source()` or runtime analysis APIs | no evaluation state is created |
| Create many runs with the same policy | `FrameFactory` or `Config.frame_factory()` | close every created Frame |

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
Module or use `config.frame_factory()`, then create and close a Frame in the
usual way. `using` declarations expand other configuration sources in source
order; later definitions win while origin and history remain available for
diagnostics.

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
5. Close every Frame you create, normally in `finally`.
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
