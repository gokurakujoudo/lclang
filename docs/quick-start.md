# Quick Start Guide

An LCL `Module` stores named expressions without evaluating them. A `Frame`
supplies host values and evaluates definitions lazily, resolving references to
other definitions as needed.

```python
import asyncio

import lclang


async def main() -> None:
    module = lclang.define_module(
        "welcome",
        {
            "greeting": 'f"Hello, {name}!"',
            "result": "greeting + ' Welcome to lclang.'",
        },
    )
    frame = lclang.define_frame(module, preset={"name": "Ada"})
    try:
        assert await frame.get("result") == "Hello, Ada! Welcome to lclang."
        assert await frame.get("greeting") == "Hello, Ada!"
    finally:
        await frame.close()


asyncio.run(main())
```

`define_module` parses all definitions up front. `define_frame` creates an
independent cache. Asking for `result` evaluates `greeting` first; the second
lookup returns its cached snapshot. Closing the Frame releases its owned tasks
and resources.

For one expression in synchronous code:

```python
import lclang

assert lclang.evaluate_sync("(value -> value * 2)(21)") == 42
```

Async code can parse once and evaluate with an explicit resolver:

```python
import asyncio

import lclang


async def evaluate() -> None:
    expression = lclang.parse_expression("subtotal + tax")
    assert await lclang.evaluate(expression, {"subtotal": 40, "tax": 2}) == 42


asyncio.run(evaluate())
```

Next, use the [tutorials and examples](tutorials/README.md), or consult the
[reference index](reference/README.md).
