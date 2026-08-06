# Runtime quickstart

This guide uses the implemented 0.1 expression and runtime API. The code is
complete and tested, but the distribution still reports development version
`0.0.0` until the 0.1 release-candidate gate passes.

## Build a module and Frame

An LCL `Module` is an immutable mapping from definition names to parsed custom
AST expressions. A `FrameFactory` creates independent lazy runtime Frames. The
reviewed `STANDARD_PRESET` supplies `iter`, `text`, `data`, and `json`
namespaces without ambient file, network, environment, or import access.

```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.Module(
        pylcl.ModuleName("quickstart"),
        {
            "result": pylcl.parse_expression(
                'json.encode({"message": "hello pylcl"})'
            )
        },
    )
    frame = pylcl.FrameFactory(module, pylcl.STANDARD_PRESET).create(
        pylcl.FrameId("quickstart:1"),
    )
    try:
        print(await frame.get("result"))
        snapshot = frame.dependency_snapshot("result")
        print(",".join(str(edge.target) for edge in snapshot.dynamic_edges))
    finally:
        await frame.close()


asyncio.run(main())
```

The first `get` evaluates and caches `result`. Later calls return that snapshot.
The dependency snapshot records that evaluation actually resolved the `json`
namespace. Static analysis retains the same source occurrence for diagnostics.

## Cache, recalculate, and inspect

`await frame.recalculate("result")` atomically replaces only `result`. It never
invalidates cached dependants. While refresh runs, ordinary readers and
`dependency_snapshot` see the old value and trace. Success or ordinary failure
publishes the new outcome and trace together; cancellation preserves both old
snapshots.

Snapshots contain `static_edges`, observed `dynamic_edges`, and a reconciliation
with `confirmed`, `inactive`, and `unexpected` partitions. Parent-owned
definitions are always evaluated, cached, inspected, recalculated, and closed
by their owner Frame.

## Limits and cleanup

Pass `EvaluationLimits` to a factory or Frame to cap AST depth, work steps, and
materialized collection size. Always await `close()` in `finally`: it cancels
owned work, then closes cached sync/async resources once in reverse order.
Cancelling one close waiter does not cancel the owner cleanup task.

For the complete surface and error model, read the
[runtime API guide](../reference/runtime-api.md).
