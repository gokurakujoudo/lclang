# Expressions and values

An LCL expression is the smallest useful unit in lclang. It receives named
values, performs one explicit calculation, and produces one value. Start here
when you want LCL's expression rules without the reusable runtime structure of
a Module and Frame.

## What you will learn

- when to use `evaluate_sync` and when to use async `evaluate`;
- how Python parameters become named LCL inputs;
- how to grow one calculation from arithmetic into structured output;
- how parsing once separates validation from repeated evaluation.

## Start with arithmetic

Pass the expression and a dictionary of host values to `evaluate_sync`.

<!-- lclang-doc-exec -->
```python
import lclang

result = lclang.evaluate_sync(
    "unit_price * quantity",
    {"unit_price": 6, "quantity": 4},
)

assert result == 24
```

The resolver supplies `6` for `unit_price` and `4` for `quantity`. LCL applies
the multiplication operator to those two values, so the assertion receives
`24`.

Names are required inputs, not implicit globals. Removing `quantity` produces
an `LclNameError`. Adding an unused parameter is harmless, but a narrow input
dictionary makes the policy easier to understand and audit.

## Add policy and structured output

Now keep the same inputs but add a discount, a threshold comparison, and a
dictionary result. LCL dictionary values are ordinary expressions, so related
results can be returned together without inventing a Python result class.

<!-- lclang-doc-exec -->
```python
import lclang

order = lclang.evaluate_sync(
    "{"
    "'subtotal': unit_price * quantity, "
    "'discount': unit_price * quantity * discount_rate, "
    "'total': unit_price * quantity * (1 - discount_rate), "
    "'large_order': quantity >= large_order_quantity"
    "}",
    {
        "unit_price": 12,
        "quantity": 5,
        "discount_rate": 0.10,
        "large_order_quantity": 10,
    },
)

assert order == {
    "subtotal": 60,
    "discount": 6.0,
    "total": 54.0,
    "large_order": False,
}
```

Each dictionary value is evaluated from the same four inputs. The subtotal is
`12 * 5 = 60`; the discount is `60 * 0.10 = 6`; and the total applies the
remaining `0.90` factor to get `54`. Finally, `5 >= 10` is false, producing the
four fields checked by the assertion.

Change `quantity` to `12` and the same expression returns a subtotal of `144`,
a total of `129.6`, and `large_order: True`. The expression defines the shape
and relationship; parameters provide the flexibility.

## Parse once for async repeated evaluation

Async applications should parse stable source during setup, then await
`evaluate` with a resolver for each run. This example adds filtering, a
comprehension, and a per-run multiplier.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


EXPRESSION = lclang.parse_expression(
    "[value * factor for value in values if value > minimum]"
)


async def main() -> None:
    first = await lclang.evaluate(
        EXPRESSION,
        {"values": [1, 2, 3, 4], "factor": 10, "minimum": 2},
    )
    second = await lclang.evaluate(
        EXPRESSION,
        {"values": [-2, 0, 2, 5], "factor": 3, "minimum": 0},
    )
    assert first == [30, 40]
    assert second == [6, 15]


asyncio.run(main())
```

In the first run the filter removes `1` and `2`, then multiplies `3` and `4` by
`10`. In the second run it removes the non-positive values, then multiplies `2`
and `5` by `3`. The AST is shared, but its resolver inputs lead to the two
different asserted lists.

Parsing validates the syntax once. Each evaluation still gets independent
values. Use a Module next when expressions need stable names and dependencies
such as `total -> subtotal -> unit_price`.

## Choose the boundary deliberately

| Situation | Use |
| --- | --- |
| One result in synchronous code | `evaluate_sync(source, values)` |
| One parsed expression in async code | `await evaluate(ast, resolver)` |
| Several related named definitions | Module plus Frame |
| File-backed definitions with provenance | `load_config` |
| Syntax tooling without evaluation | `parse_expression` and `to_source` |

`evaluate_sync` owns a temporary event loop and rejects use inside an already
running loop. Direct async evaluation has no Frame cache or hierarchy. These
are useful constraints: choose the smallest boundary that owns exactly the
state your calculation needs.

[Next: Modules and Frames](02-modules-and-frames.md) | [Return to the series introduction](README.md)
