# Async Python integration

lclang is async-first because configuration often selects work that is already
asynchronous: service discovery, pricing, calendar loading, or resource use.
Host values may be immediate or awaitable, and host callables may return either.

## What you will learn

- how LCL automatically awaits host calls;
- how lazy branches prevent unnecessary async work;
- how expression-form `with` manages sync or async resources;
- how Frame ownership differs from host capability ownership.

## Await a host function only when selected

The host owns the exchange-rate provider. LCL owns the policy that decides
whether to call it and how to use its result.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


PRICING = lclang.define_module(
    "pricing",
    {
        "subtotal": "unit_price * quantity",
        "converted": (
            "subtotal if currency == 'USD' "
            "else subtotal * exchange_rate(currency)"
        ),
        "label": 'f"{currency} {converted:.2f}"',
    },
)


async def main() -> None:
    calls: list[str] = []

    async def exchange_rate(currency: str) -> float:
        calls.append(currency)
        await asyncio.sleep(0)
        return {"EUR": 0.92, "GBP": 0.79}[currency]

    async with lclang.define_frame(
        PRICING,
        preset={
            "unit_price": 20,
            "quantity": 3,
            "currency": "GBP",
            "exchange_rate": exchange_rate,
        },
    ) as frame:
        assert await frame.get("subtotal") == 60
        assert calls == []
        assert await frame.get("label") == "GBP 47.40"
        assert calls == ["GBP"]


asyncio.run(main())
```

The direct subtotal lookup only multiplies `20 * 3`, so it never reaches
`exchange_rate`. Resolving `label` then follows `converted`; because the
currency is GBP, the conditional awaits `0.79`, multiplies it by `60`, and
formats `47.4` with two decimal places. Recording one call proves the lazy
boundary.

lclang recursively resolves awaitables returned by lookup, calls, iteration,
and context-manager protocols. It does not add a timeout to blocking Python
code; host implementations remain responsible for their own I/O policy.

## Acquire and release an async resource

LCL `with` is an expression. It prefers an async context-manager protocol when
available, binds the entered value, evaluates the body, and awaits cleanup.

<!-- lclang-doc-exec -->
```python
import asyncio

import lclang


class Session:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def __aenter__(self) -> "Session":
        self.events.append("open")
        return self

    async def __aexit__(self, *details: object) -> bool:
        del details
        self.events.append("close")
        return False

    async def fetch(self, key: str) -> int:
        self.events.append(f"fetch {key}")
        return {"inventory": 7}[key]


async def main() -> None:
    events: list[str] = []
    node = lclang.parse_expression(
        "with open_session() as session: session.fetch(key) * requested"
    )
    result = await lclang.evaluate(
        node,
        {
            "open_session": lambda: Session(events),
            "key": "inventory",
            "requested": 3,
        },
    )
    assert result == 21
    assert events == ["open", "fetch inventory", "close"]


asyncio.run(main())
```

The `with` expression awaits `__aenter__`, binds the returned Session, and then
awaits `fetch("inventory")`. That call returns `7`, the body multiplies it by
the requested `3`, and cleanup runs before the result `21` is returned. The
event assertion verifies the exact open, use, close sequence.

If acquisition or the body fails, previously entered managers unwind in reverse
order. Ordinary host exceptions become source-aware `LclEvaluationError`
instances; cancellation remains cancellation after required cleanup.

## Keep the boundary narrow

Expose `exchange_rate(currency)` rather than a complete payments container.
Expose `open_session()` rather than ambient network access. LCL can be creative
with the capabilities supplied to it, but cannot invent capabilities that are
not in its Frame hierarchy.

An owned Frame should itself be used with `async with`. Frame close cancels and
settles its in-flight definition tasks and closes cached result resources that
provide `close` or `aclose`. Host values supplied directly are borrowed and are
not automatically closed.

[Previous: Configuration files](04-configuration-files.md) | [Next: Caching and recalculation](06-caching-and-recalculation.md) | [Return to the series introduction](README.md)
