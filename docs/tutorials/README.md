# Learn lclang: start here

lclang is for configuration that has relationships, not just stored values. A
service URL depends on an environment. A price depends on quantity, customer
policy, and perhaps an asynchronous rate provider. Those relationships should
stay visible and testable without becoming scattered Python glue.

LCL stands for **Lazy Context Language**:

- **Lazy:** a definition runs only when a requested result needs it.
- **Context:** the same definitions can receive different inputs for each
  request, command, tenant, or test.
- **Language:** relationships are parsed into lclang's own immutable syntax and
  interpreted by its async runtime. They are not passed to Python `eval` or
  `exec`.

This introduction gives you a working mental model and four complete examples.
They progress from a one-line calculation to a reusable, file-backed pricing
policy. By the end, you should know whether lclang fits your problem and which
tutorial to read next.

> **The lclang philosophy:** lclang defines a **strong way of working** and
> provides strong **flexibility within that way**. It does not invite every
> application to invent its own parsing, lookup, caching, and lifecycle rules.
> It fixes those rules, then lets you be creative with definitions, dependency
> shapes, parameters, host capabilities, and outputs. The result is expressive
> configuration that remains recognizable, inspectable, and testable.

Every chapter is published, and the documentation tests execute each marked
example directly from its Markdown source.

## The tutorial series

0. **Start here: mental model and first application** (this page) -- decide when
   lclang is useful, then follow the path from one expression to a configuration
   file.
1. **[Expressions and values](01-expressions-and-values.md)** -- name calculations in a Module and evaluate
   them with host inputs and canonical builtins in a Frame.
2. **[Modules and Frames](02-modules-and-frames.md)** -- define policy once, evaluate it in many independent
   contexts, and manage each context's lifecycle.
3. **[The LCL language](03-language.md)** -- build expressions with collections, conditionals,
   comprehensions, formatted strings, arrow functions, and control forms.
4. **[Configuration files](04-configuration-files.md)** -- write `.lclcfg`, compose files with `using`, keep
   source provenance, and control loading.
5. **[Async Python integration](05-async-python-integration.md)** -- expose narrow host functions, await external
   work automatically, and clean up resources deterministically.
6. **[Caching and recalculation](06-caching-and-recalculation.md)** -- reason about lazy success and failure
   snapshots, concurrency sharing, mixins, and explicit refresh.
7. **[Errors and inspection](07-errors-and-inspection.md)** -- preserve source-aware diagnostics and explain a
   value without accidentally evaluating it.
8. **[Dependency analysis](08-dependency-analysis.md)** -- compare possible static dependencies with lookups
   observed during a real evaluation.
9. **[Command-line applications](09-command-line-applications.md)** -- combine typed commands, configuration,
   overrides, dry runs, logging, and stable exit behavior.
10. **[Workflow status](10-workflow-status.md)** -- report nested task and step outcomes while preserving
    failure and cleanup semantics.
11. **[Business-day calendars](11-business-day-calendars.md)** -- compose three-state calendars, map dates, and
    load named policies from strict JSON.
12. **[Production patterns](12-production-patterns.md)** -- organize modules, factories, tests, limits, trust
    boundaries, and application ownership.
13. **[Scoped values and Frame evaluation](13-scoped-values-and-frame-evaluation.md)** -- organize qualified
    bindings through lazy proxies, materialize override-friendly dataclass lists,
    and run unnamed expressions in an existing Frame.
14. **[Tree workflows](14-tree-workflows.md)** -- connect typed async actions, scoped resources, explicit
    data flow, status, cleanup, and CLI inference in one inspectable task tree.
15. **[Case Study: Energy Settlement Workflow](15-energy-settlement-workflow.md)** -- build and exercise a complete
    configured workflow command with result files, logs, masking, overrides, dry-run, verbose, and errors.
16. **[Python utilities for downstream applications](16-python-utilities.md)** -- use the live environment,
    standalone logging, reviewed data helpers, and calendars without adopting LCL evaluation or the CLI.
17. **[Configuration composition](17-configuration-composition.md)** -- choose shared expansion or isolated
    imports, supply required and runtime values, compose Modules, and trace loading and evaluation failures.

The sequence is deliberate: lessons 1-4 establish everyday use, lessons 5-8
make behavior predictable in real applications, and lessons 9-15 apply the same
model to larger systems. Lesson 16 shows which supporting Python APIs can
stand alone, and lesson 17 brings configuration composition and diagnostics
together. Read the lessons in order or jump to one topic after
finishing this introduction.

## Is lclang a good fit?

Use lclang when all or most of these statements are true:

- Your configuration contains derived values that must stay consistent.
- Stable policy should be reusable with different per-run Python inputs.
- Some calculations are optional, expensive, or asynchronous.
- You need to inspect definitions, dependencies, cached values, or failures.
- Configuration authors and host callables are trusted by the application.

Prefer JSON, TOML, YAML, or ordinary Python data when the values are already
static. Do not use LCL as a sandbox for hostile input. The interpreter avoids
Python dynamic-code execution, but trusted host values and callables still have
the authority your application gives them.

## The two ideas to remember

A `Module` is an immutable collection of named, unevaluated definitions. It
answers **what can be calculated?**

A `Frame` combines a Module with inputs, name lookup, a lazy result cache, and
owned asynchronous work. It answers **what do those definitions mean for this
run?**

```text
                        define once
Python/LCL source  ---------------------->  Module
                                                  \
                                                   + inputs for one run
                                                  /
                        evaluate lazily           v
requested name  --------------------------->  Frame  ----> value snapshot
```

Modules are safe to reuse because they have no evaluation state. Frames are
intentionally stateful and belong to one event loop. Create a fresh Frame for
each independent run and use `async with` so its work is closed cleanly.

## Before you begin

lclang requires Python 3.14 or newer and has no third-party runtime
dependencies.

```console
python -m pip install lclang
```

The examples use assertions so that success is unambiguous. Save any complete
Python block as a `.py` file and run it; no output means every documented result
was correct.

## Example 1: calculate one expression

Name the result in a Module, then create a Frame with inputs for one run.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.lang import define_frame, define_module


TOTAL = define_module("total", {"result": "unit_price * quantity"})


async def main() -> None:
    async with define_frame(
        TOTAL,
        preset={"unit_price": 6, "quantity": 4},
    ) as frame:
        assert await frame.get("result") == 24


asyncio.run(main())
```

`unit_price` resolves to `6` and `quantity` resolves to `4` from the Frame's
`preset`. Requesting `result` follows those lookups and multiplies them to
produce `24`. Leaving the context closes the Frame and its owned work.

lclang parses the source into its own immutable abstract syntax tree and then
interprets it in the Frame with the supplied values and canonical builtins.
Names are explicit: if `quantity` is missing, evaluation raises `LclNameError`
instead of silently inventing a default.

`asyncio.run(main())` starts the event loop at a synchronous application's
outer boundary. Servers, workers, and other async applications await their
coroutine in the existing loop. The Module and Frame APIs stay the same.

## Example 2: define once, evaluate in context

Suppose a deployment tool needs a URL and timeout for several environments.
The relationships are stable, while `service` and `environment` change for
each run.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.lang import define_frame, define_module


SERVICE_POLICY = define_module(
    "service-policy",
    {
        "summary": 'f"{base_url} (timeout={timeout}s)"',
        "base_url": 'f"https://{host}/v1"',
        "host": 'f"{service}.{environment}.example.com"',
        "timeout": "30 if environment == 'production' else 5",
    },
)


async def describe(service: str, environment: str) -> str:
    async with define_frame(
        SERVICE_POLICY,
        preset={"service": service, "environment": environment},
    ) as frame:
        result = await frame.get("summary")
        assert isinstance(result, str)
        return result


async def main() -> None:
    assert await describe("billing", "test") == (
        "https://billing.test.example.com/v1 (timeout=5s)"
    )
    assert await describe("billing", "production") == (
        "https://billing.production.example.com/v1 (timeout=30s)"
    )


asyncio.run(main())
```

For the test run, `host` joins `billing`, `test`, and the fixed domain;
`base_url` adds the scheme and path; and the false conditional branch selects a
five-second timeout. The production Frame repeats the same dependency path with
different inputs, and its true branch selects `30`. The two assertions show the
complete strings produced at the end of those paths.

Three details matter here:

1. `define_module` parses every definition up front. A malformed expression
   fails during application setup, not halfway through a request.
2. Definition order is irrelevant. Asking for `summary` makes the Frame follow
   `summary -> base_url -> host` and `summary -> timeout` as needed.
3. The Module is reused, but each call creates a fresh Frame with independent
   inputs, cached results, dependency observations, and lifecycle.

The `preset` name means host-provided bindings; it does not mutate the Module.
Keep this boundary narrow. Pass the primitive values and purpose-built
functions that policy needs rather than exposing an entire application object.

## Example 3: skip work that is not needed

Lazy evaluation becomes valuable when a host function performs asynchronous or
expensive work. This pricing policy converts a subtotal only for non-USD
orders. lclang automatically awaits an async host function when the selected
branch calls it.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.lang import define_frame, define_module


PRICING = define_module(
    "pricing",
    {
        "subtotal": "unit_price * quantity",
        "converted_total": (
            "subtotal if currency == 'USD' "
            "else subtotal * exchange_rate(currency)"
        ),
        "label": 'f"{currency} {converted_total:.2f}"',
    },
)


async def main() -> None:
    calls: list[str] = []

    async def exchange_rate(currency: str) -> float:
        calls.append(currency)
        return {"EUR": 0.92}[currency]

    async with define_frame(
        PRICING,
        preset={
            "unit_price": 10,
            "quantity": 3,
            "currency": "EUR",
            "exchange_rate": exchange_rate,
        },
    ) as euro_frame:
        assert await euro_frame.get("subtotal") == 30
        assert calls == []

        assert await euro_frame.get("label") == "EUR 27.60"
        assert calls == ["EUR"]

        assert await euro_frame.get("label") == "EUR 27.60"
        assert calls == ["EUR"]  # The value is a cached snapshot.

    async with define_frame(
        PRICING,
        preset={
            "unit_price": 10,
            "quantity": 3,
            "currency": "USD",
            "exchange_rate": exchange_rate,
        },
    ) as usd_frame:
        assert await usd_frame.get("label") == "USD 30.00"
        assert calls == ["EUR"]  # The USD branch never calls the provider.


asyncio.run(main())
```

The EUR Frame first multiplies `10 * 3`, so requesting only `subtotal` leaves
the provider untouched. Requesting `label` reaches `converted_total`, selects
the non-USD branch, awaits the `0.92` rate, and formats `27.6` as `27.60`. The
second `label` read uses that snapshot. In the USD Frame the conditional returns
the subtotal directly, so the provider call list still contains only `EUR`.

The first request for a definition stores either its value or its ordinary
failure. Later reads in that Frame receive the same snapshot, and concurrent
callers in the same event loop share in-flight work. A new Frame starts a new
run.

This is deliberately not spreadsheet-style reactivity. Changing an input does
not invalidate downstream snapshots behind your back. Later tutorials will
show when to create a new Frame and when explicit `mixin` plus `recalculate` is
the clearer choice.

## Example 4: move policy into a configuration file

Once non-Python users should edit the policy, or source locations matter for
diagnostics, put definitions in a UTF-8 `.lclcfg` file. Create
`pricing.lclcfg` beside the Python program:

<!-- lclang-intro-config -->
```lclcfg
__LCL_VERSION__: 1

subtotal: unit_price * quantity
discount: subtotal * discount_rate if vip else 0
total: subtotal - discount
message: f"{customer}: {currency} {total:.2f}"
```

Each definition has a name, a colon, and one complete LCL expression. The file
stores relationships, while the application still owns request-specific
values.

<!-- lclang-intro-config-exec -->
```python
import asyncio
from pathlib import Path

from lclang.config import load_config


async def main(config_path: Path) -> None:
    config = await load_config(config_path)
    async with config.to_frame(
        preset={
            "unit_price": 25,
            "quantity": 4,
            "discount_rate": 0.10,
            "vip": True,
            "customer": "Ada",
            "currency": "USD",
        },
    ) as frame:
        assert await frame.get("message") == "Ada: USD 90.00"


if __name__ == "__main__":
    asyncio.run(main(Path("pricing.lclcfg")))
```

The supplied values make `subtotal` equal to `25 * 4`, or `100`. Because `vip`
is true, `discount` becomes ten percent of that subtotal. `total` subtracts
`10` from `100`, and the f-string combines the customer, currency, and
two-decimal value into the asserted `Ada: USD 90.00` message.

This example uses no dynamic `using` target, so `load_config` does not evaluate
its definitions. Dynamic targets can evaluate earlier definitions in temporary
Frames to choose an included file. The immutable result keeps source provenance
for diagnostics and can be reused. `config.to_frame(preset=...)` preserves that
source information and supplies the same canonical lookup, caching, and lifecycle
as `define_frame(config.to_module(), preset=...)`. Request further names from the
same Frame when they should share snapshots in one run.

Larger configurations can compose files with source-ordered `using`
declarations. That belongs in the focused configuration tutorial; the important
boundary for now is simple: the file defines trusted policy, and Python supplies
only the context for the current run.

## What you have built

The four examples use the same design at increasing scale:

```text
one expression
    -> related named definitions
        -> lazy asynchronous host integration
            -> file-backed reusable policy with source provenance
```

The design stays understandable because parsing, reusable definitions, per-run
inputs, cached evaluation, and cleanup have separate owners. That separation is
the core of lclang's code structure too: lexer/parser and immutable AST,
interpreter, runtime Module/Frame layer, configuration loader, then optional
application frameworks such as CLI, workflow, and calendars.

Keep these rules nearby:

1. Parse or load stable definitions once.
2. Create one Frame for each independent run.
3. Supply only the values and functions the policy needs.
4. Ask only for the outputs you need; evaluation follows dependencies lazily.
5. Treat cached results as snapshots, not reactive cells.
6. Use owned Frames as async context managers.
7. Catch `lclang.error.LclError` at an application boundary when you need one family
   for expected language, configuration, and runtime failures.
8. Treat LCL source and host capabilities as trusted configuration.

For exact syntax and API contracts, use the [reference index](../reference/README.md).
For an even smaller first run, see the [Quick Start Guide](../quick-start.md).
