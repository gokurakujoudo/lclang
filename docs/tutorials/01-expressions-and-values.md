# Expressions and values

An LCL expression calculates a value from named inputs. Give that expression a
name with `define_module`, create its context with `define_frame`, and request
the result with `frame.get`. This is the same path for one arithmetic result
and a larger configuration.

## What you will learn

- how to define and request one calculated value;
- how Python values become named LCL inputs through a preset;
- how to grow arithmetic into structured output;
- how to reuse validated expressions with fresh inputs and independent snapshots.

## Start with arithmetic

A Module names the calculation. A Frame supplies the inputs and owns the
calculated result. Use `asyncio.run` at a synchronous script's outer boundary;
inside an async application, await its coroutine in the existing event loop.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


CALCULATION = lclang.define_module("calculation", {"total": "unit_price * quantity"})


async def main() -> None:
    async with lclang.define_frame(
        CALCULATION,
        preset={"unit_price": 6, "quantity": 4},
    ) as frame:
        assert await frame.get("total") == 24
        assert await frame.get("total") == 24


asyncio.run(main())
```

The preset supplies `6` for `unit_price` and `4` for `quantity`. The first
`get("total")` multiplies them and stores `24` as a named snapshot. The second
lookup reuses that snapshot. Leaving the `async with` block closes the Frame
and settles its owned asynchronous work.

Application input names are explicit bindings. Removing `quantity` produces an
`LclNameError`; an unused input is harmless. Canonical Frames also provide
reviewed builtins such as `int`, `len`, and `sum`, so ordinary builtins need no
manual injection into the preset.

## Add policy and structured output

Keep the same input model, then add a discount, a threshold comparison, and a
dictionary result. Separate named expressions let related results reuse their
dependencies.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


ORDER = lclang.define_module(
    "order",
    {
        "subtotal": "unit_price * quantity",
        "discount": "subtotal * discount_rate",
        "total": "subtotal - discount",
        "large_order": "quantity >= large_order_quantity",
        "summary": (
            "{'subtotal': subtotal, 'discount': discount, "
            "'total': total, 'large_order': large_order}"
        ),
    },
)


async def main() -> None:
    async with lclang.define_frame(
        ORDER,
        preset={
            "unit_price": 12,
            "quantity": 5,
            "discount_rate": 0.10,
            "large_order_quantity": 10,
        },
    ) as frame:
        assert await frame.get("summary") == {
            "subtotal": 60,
            "discount": 6.0,
            "total": 54.0,
            "large_order": False,
        }
        assert await frame.get("total") == 54.0


asyncio.run(main())
```

Requesting `summary` follows its named dependencies. The subtotal is
`12 * 5 = 60`; the discount is `60 * 0.10 = 6`; and subtracting that discount
gives `54`. The comparison `5 >= 10` is false. Each definition becomes a
snapshot in the same Frame, so the final `total` lookup reuses `54.0`.

Definition order does not control evaluation order. Creating the Module
validates every expression; requesting a result evaluates only the names it
needs.

## Reuse a Module with new inputs

A Module has no per-run cache. Reuse it for a second run by creating a fresh
Frame with a new preset. This example combines filtering, a comprehension,
and a per-run multiplier.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


TRANSFORM = lclang.define_module(
    "transform",
    {"selected": "[value * factor for value in values if value > minimum]"},
)


async def main() -> None:
    async with lclang.define_frame(
        TRANSFORM,
        preset={"values": [1, 2, 3, 4], "factor": 10, "minimum": 2},
    ) as first:
        assert await first.get("selected") == [30, 40]
    async with lclang.define_frame(
        TRANSFORM,
        preset={"values": [-2, 0, 2, 5], "factor": 3, "minimum": 0},
    ) as second:
        assert await second.get("selected") == [6, 15]


asyncio.run(main())
```

The first Frame removes `1` and `2`, then multiplies `3` and `4` by `10`. The
second removes the non-positive values and multiplies `2` and `5` by `3`.
Both Frames use the same validated expressions, but each owns its inputs and
result snapshots. Changing host inputs does not silently invalidate an
existing Frame's calculated results; use a fresh Frame for an independent run.

## Choose the next step

| Situation | Use |
| --- | --- |
| One calculation or related named definitions | `define_module`, `define_frame`, and `frame.get` |
| An unnamed expression over an existing Frame | `await frame.evaluate(source)` |
| File-backed definitions with provenance | `load_config` |
| Syntax tooling without evaluation | `parse_expression` and `to_source` |

The next chapter develops Module reuse, lookup hierarchy, and Frame ownership.
Every calculation keeps the same named definition and context boundary.

[Next: Modules and Frames](02-modules-and-frames.md) | [Return to the series introduction](README.md)
