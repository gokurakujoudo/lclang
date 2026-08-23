# Caching and recalculation

A Frame is a record of one calculation run, not a reactive spreadsheet. The
first lookup stores a success or ordinary failure snapshot. Recalculation is
explicit, atomic, and limited to the selected definition.

## What you will learn

- how lazy value snapshots work;
- how concurrent callers share one in-flight calculation;
- why changing an input does not invalidate dependants;
- when a new Frame is clearer than targeted recalculation.

## Share one calculation across concurrent callers

Two callers request the same definition before it finishes. The Frame creates
one owner task, shields it from individual waiter cancellation, and publishes
one result for later reads.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    calls = 0
    release = asyncio.Event()

    async def load_price() -> int:
        nonlocal calls
        calls += 1
        await release.wait()
        return 40

    module = lclang.define_module(
        "quote",
        {"price": "load_price()", "total": "price * quantity"},
    )
    async with lclang.define_frame(
        module,
        preset={"load_price": load_price, "quantity": 3},
    ) as frame:
        first = asyncio.create_task(frame.get("total"))
        second = asyncio.create_task(frame.get("total"))
        await asyncio.sleep(0)
        release.set()
        assert await asyncio.gather(first, second) == [120, 120]
        assert await frame.get("total") == 120
        assert calls == 1


asyncio.run(main())
```

Both `total` requests converge on the same in-flight `price` definition. Once
released, `load_price` returns `40`; `quantity` scales it to `120`, and the
Frame publishes that snapshot to both waiters. The later read uses the same
snapshot, which is why the provider counter remains `1`.

Failure snapshots behave the same way for ordinary exceptions: the next read
raises the stored structured failure rather than repeating host work.

## Refresh only what you name

`mixin` updates local host values. Existing cached definitions remain exactly
as they were until explicitly recalculated.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    module = lclang.define_module(
        "invoice",
        {
            "subtotal": "unit_price * quantity",
            "total": "subtotal + shipping",
            "label": 'f"USD {total:.2f}"',
        },
    )
    async with lclang.define_frame(
        module,
        preset={"unit_price": 10, "quantity": 3, "shipping": 5},
    ) as frame:
        assert await frame.get("label") == "USD 35.00"

        frame.mixin({"unit_price": 20})
        assert await frame.recalculate("subtotal") == 60
        assert await frame.get("total") == 35
        assert await frame.get("label") == "USD 35.00"

        assert await frame.recalculate("total") == 65
        assert await frame.recalculate("label") == "USD 65.00"


asyncio.run(main())
```

The original chain computes `10 * 3 + 5 = 35`. Mixing in `20` changes only the
host input. Recalculating `subtotal` produces `60`, but the already cached
`total` and `label` remain `35`. Refreshing those definitions in dependency
order finally produces and formats `65`.

This rule is intentionally strong: recalculation never silently invalidates
dependants. The application chooses the refresh order and therefore can explain
the resulting state.

## New Frame or recalculation?

Create a new Frame when inputs represent a new request, tenant, scenario, or
complete policy run. Use `mixin` plus `recalculate` when preserving other
snapshots is intentional—for example, refreshing one market quote while keeping
the rest of an audit snapshot fixed.

Recalculation publishes atomically. Ordinary reads keep seeing the old snapshot
until the refresh succeeds or commits a new failure. Concurrent recalculation
callers share one refresh owner. Cancellation commits nothing and leaves the
previous snapshot available.

[Previous: Async Python integration](05-async-python-integration.md) | [Next: Errors and inspection](07-errors-and-inspection.md)
