# Production patterns

Production lclang code is easiest to reason about when parsing, per-run values,
host capabilities, limits, diagnostics, and cleanup have explicit owners. The
same strong structure used in small examples scales to services and tools.

## What you will learn

- how to parse policy once and create independent runs through a factory;
- how presets and call values express stable versus transient context;
- how to place limits and error handling at application boundaries;
- how to test policy without external side effects.

## Package reusable runtime policy

A `FrameFactory` retains immutable construction policy. Presets hold stable host
bindings; `create(values=...)` adds or replaces per-run inputs.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


ORDER = lclang.define_module(
    "order",
    {
        "subtotal": "unit_price * quantity",
        "discount": "subtotal * discount_rate if vip else 0",
        "total": "subtotal - discount",
        "result": 'f"{region}/{currency} {total:.2f}"',
    },
)
DEFAULTS = lclang.Preset(
    "order-defaults",
    {"discount_rate": 0.10, "region": "global", "currency": "USD"},
)
FACTORY = lclang.FrameFactory(
    ORDER,
    DEFAULTS,
    lclang.EvaluationLimits(
        max_depth=100,
        max_steps=10_000,
        max_collection_items=1_000,
    ),
)


async def price(*, quantity: int, vip: bool, region: str | None = None) -> str:
    values: dict[str, object] = {
        "unit_price": 25,
        "quantity": quantity,
        "vip": vip,
    }
    if region is not None:
        values["region"] = region
    async with FACTORY.create(values=values) as frame:
        result = await frame.get("result")
        assert isinstance(result, str)
        return result


async def main() -> None:
    assert await price(quantity=2, vip=False) == "global/USD 50.00"
    assert await price(quantity=4, vip=True, region="eu") == "eu/USD 90.00"


asyncio.run(main())
```

The regular order uses preset region and currency, computes `25 * 2`, and skips
the VIP discount. The second call overrides only `region`; `25 * 4` produces
`100`, the true VIP branch subtracts ten percent, and `result` formats the
remaining `90` with the EU label.

The Module, Preset, factory, and limits are immutable reusable policy. Every
created Frame still has fresh caches, tasks, traces, and lifecycle state. A raw
factory has no canonical builtin parent unless one is supplied, so this example
uses only its explicit values.

## Load once, test many realistic scenarios

File-backed policy can use the same factory pattern. The test controls file I/O
with a temporary directory and covers sunny, alternate, and rainy inputs.

<!-- lclang-doc-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import lclang
from lclang.config import load_config


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-production-tutorial-") as directory:
        path = Path(directory) / "capacity.lclcfg"
        path.write_text(
            "requested: replicas * capacity_per_replica\n"
            "accepted: requested <= hard_limit\n"
            'decision: "accept" if accepted else "reject"\n',
            encoding="utf-8",
        )
        config = await load_config(path)
        factory = config.frame_factory(
            limits=lclang.EvaluationLimits(max_collection_items=100)
        )

        scenarios = [
            ({"replicas": 2, "capacity_per_replica": 20, "hard_limit": 100}, "accept"),
            ({"replicas": 6, "capacity_per_replica": 20, "hard_limit": 100}, "reject"),
        ]
        for values, expected in scenarios:
            async with factory.create(values=values) as frame:
                assert await frame.get("decision") == expected
                assert frame.inspect_variable("requested").definition is not None

        async with factory.create(
            values={"replicas": 2, "capacity_per_replica": 20}
        ) as missing:
            try:
                await missing.get("decision")
            except lclang.LclNameError as error:
                assert "hard_limit" in str(error)
            else:
                raise AssertionError("missing host input was accepted")


asyncio.run(main())
```

The first scenario requests `40`, so `40 <= 100` selects `accept`. The second
requests `120`, making the comparison false and selecting `reject`. The final
Frame cannot resolve `hard_limit` while evaluating `accepted`; the resulting
`LclNameError` is caught at the scenario boundary and checked for the missing
input name.

## Production checklist

1. Parse Modules or load Configs once during application setup.
2. Create one Frame per independent request, command, tenant, or scenario.
3. Pass plain values and narrow purpose-built host callables.
4. Mock external connectivity and isolate file inputs in tests.
5. Set evaluation and configuration-loading limits appropriate to the policy.
6. Inspect before evaluating when diagnosis must remain side-effect free.
7. Catch `LclError` at the boundary that can log, translate, or recover.
8. Treat cached values as snapshots; create a new Frame for a new run.
9. Close every owned Frame deterministically with `async with`.
10. Treat LCL sources and supplied host capabilities as trusted configuration.

The pattern is opinionated on purpose. Applications gain flexibility through
definitions and controlled inputs, not by bypassing the runtime's ownership,
inspection, and lifecycle rules.

[Previous: Business-day calendars](11-business-day-calendars.md) | [Next: Scoped values and Frame evaluation](13-scoped-values-and-frame-evaluation.md) | [Return to the series introduction](README.md)
