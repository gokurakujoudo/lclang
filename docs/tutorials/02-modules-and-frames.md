# Modules and Frames

Modules and Frames are lclang's main design. A Module stores immutable named
definitions. A Frame gives those definitions concrete meaning for one run by
supplying inputs, lookup, lazy snapshots, and lifecycle ownership.

## What you will learn

- why lclang separates reusable policy from per-run context;
- how dependencies evaluate regardless of declaration order;
- how to reuse one Module across different inputs;
- how parent and child Frames express controlled lookup hierarchy.

## The philosophy: a strong form with room to create

lclang intentionally defines a **strong way of working**:

1. expressions are parsed into lclang's own immutable AST;
2. related definitions live in an immutable Module;
3. one short-lived Frame owns one evaluation context;
4. evaluation is lazy and async-first;
5. results are snapshots and cleanup is explicit.

That form is not meant to make every application identical. It provides strong
**flexibility within that way**: you choose the definitions, dependency shapes,
host values, sync or async functions, Frame hierarchy, configuration sources,
and outputs. Unlike an API that exposes arbitrary hooks everywhere, lclang
keeps creativity inside a model that remains inspectable and predictable.

```text
definitions --parse once--> Module --combine with inputs--> Frame --get--> value
                                  reusable              one independent run
```

## Define an invoice once

Definitions may refer forward or backward. Asking for `label` makes the Frame
follow only the names required to calculate it.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


INVOICE = lclang.define_module(
    "invoice",
    {
        "label": 'f"{customer}: {currency} {total:.2f}"',
        "total": "subtotal - discount + shipping",
        "subtotal": "unit_price * quantity",
        "discount": "subtotal * discount_rate",
        "shipping": "0 if subtotal >= free_shipping_at else shipping_fee",
    },
)


async def price(customer: str, quantity: int) -> str:
    async with lclang.define_frame(
        INVOICE,
        preset={
            "customer": customer,
            "currency": "USD",
            "unit_price": 25,
            "quantity": quantity,
            "discount_rate": 0.10,
            "free_shipping_at": 100,
            "shipping_fee": 8,
        },
    ) as frame:
        value = await frame.get("label")
        assert isinstance(value, str)
        return value


async def main() -> None:
    assert await price("Ada", 2) == "Ada: USD 53.00"
    assert await price("Grace", 4) == "Grace: USD 90.00"


asyncio.run(main())
```

Ada's two items produce a `50` subtotal and a `5` discount. Because `50` is
below the free-shipping threshold, the `8` fee makes the total `53`. Grace's
four items produce `100`, a `10` discount, and free shipping, so her total is
`90`. The final `label` definition formats each independently cached result.

The Module is parsed once. Each `price` call creates a fresh Frame, so Ada and
Grace never share cached values. Free shipping demonstrates flexibility inside
the fixed model: policy chooses the branch, while the Frame still owns when and
where it runs.

## Reuse context with a controlled hierarchy

A child Frame searches its local definitions and values, then its parent. A
definition always evaluates in the Frame that owns it. This prevents a child
from silently changing the meaning of a parent-owned policy.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


ENVIRONMENT = lclang.define_module(
    "environment",
    {
        "region": '"eu-west"',
        "domain": 'f"{region}.example.com"',
    },
)
SERVICE = lclang.define_module(
    "service",
    {
        "endpoint": 'f"https://{service_name}.{domain}/{version}"',
        "description": 'f"{service_name} -> {endpoint}"',
    },
)


async def main() -> None:
    async with lclang.define_frame(ENVIRONMENT) as environment:
        async with environment.derive(
            SERVICE,
            values={"service_name": "billing", "version": "v2"},
        ) as service:
            assert await service.get("endpoint") == (
                "https://billing.eu-west.example.com/v2"
            )
            assert await service.get("description") == (
                "billing -> https://billing.eu-west.example.com/v2"
            )
            assert await service.get("timeout", fallback=15) == 15
            assert service.has("region")
            assert service.get_definition("region") is not None


asyncio.run(main())
```

The child owns `endpoint`, so it starts with its local `service_name` and
`version`, then falls back to the parent-owned `domain`. That parent definition
uses its own `region` to produce `eu-west.example.com`. `description` reuses the
cached endpoint, while `timeout` returns `15` only because neither Frame defines
that name.

The fallback is returned only because `timeout` is absent from the complete
hierarchy. A failure inside an existing definition is never replaced by the
fallback. `has` and `get_definition` inspect lookup without evaluating.

## Ownership rules

- Reuse Modules; do not put request state in them.
- Create one Frame for each independent run or request.
- Use every owned Frame with `async with`.
- Treat a parent as borrowed; closing a child does not close its parent.
- Prefer `define_frame` for canonical builtins and namespaces.
- Use `FrameFactory` when construction policy itself should be reusable.

These rules create a stable skeleton. Within it, definitions may be simple
arithmetic, rich collection transformations, async service decisions, date
policy, or application-specific functions.

[Previous: Expressions and values](01-expressions-and-values.md) | [Next: The LCL language](03-language.md)
