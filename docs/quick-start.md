# Quick Start Guide

An LCL `Module` stores named expressions without evaluating them. A `Frame`
supplies host values and evaluates definitions lazily, resolving references to
other definitions as needed.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.lang import define_frame, define_module


async def main() -> None:
    module = define_module(
        "welcome",
        {
            "greeting": 'f"Hello, {name}!"',
            "result": "greeting + ' Welcome to lclang.'",
        },
    )
    async with define_frame(module, preset={"name": "Ada"}) as frame:
        assert await frame.get("result") == "Hello, Ada! Welcome to lclang."
        assert await frame.get("greeting") == "Hello, Ada!"


asyncio.run(main())
```

`define_module` parses all definitions up front. `define_frame` creates an
independent cache. Asking for `result` evaluates `greeting` first; the second
lookup returns its cached snapshot. Leaving the `async with` block closes the
Frame and releases its owned tasks and resources.

For one expression, name its result in a Module. The canonical Frame includes
reviewed builtins such as `int` and `len`, alongside your supplied inputs:

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.lang import define_frame, define_module


TOTAL = define_module("total", {"result": "int(subtotal) + len(taxes)"})


async def main() -> None:
    async with define_frame(
        TOTAL,
        preset={"subtotal": "40", "taxes": ["state", "local"]},
    ) as frame:
        assert await frame.get("result") == 42


asyncio.run(main())
```

`int` converts the host string `"40"`, and `len` counts the two supplied taxes.
The same Module and Frame APIs handle both a single calculation and a set of
related definitions. Use `asyncio.run` once at the outer boundary of a
synchronous application; async applications await their coroutine in the
existing loop.

Next, use the [tutorials and examples](tutorials/README.md), or consult the
[reference index](reference/README.md).
