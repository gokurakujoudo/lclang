# Scoped values and Frame evaluation

Scoped values organize related names without creating nested Frames. Complete
keys remain flat while each missing prefix appears as a lazy proxy over the
same Frame. An existing Frame can also evaluate a quick unnamed LCL expression
without adding a Module definition or cache entry.

## What you will learn

- how qualified keys infer lazy Frame proxies;
- why qualified leaves normally make `FRAME_PROXY` unnecessary;
- how scoped lookup, safe access, parent lookup, and caching interact;
- how Python and LCL use the same qualified paths;
- when to use `frame.evaluate` instead of `frame.get`.

## Define and read one scope

The smallest useful scope needs only a qualified leaf. Prefix proxies are
inferred automatically.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    module = lclang.define_module(
        "service",
        {
            "service.host": '"api.example.com"',
            "service.port": "8443",
            "service.url": 'f"https://{service.host}:{service.port}"',
        },
    )
    async with lclang.define_frame(module) as frame:
        assert await frame.get("service.url") == "https://api.example.com:8443"
        service = await frame.get("service")
        assert isinstance(service, lclang.FrameProxy)
        assert await service.port == 8443


asyncio.run(main())
```

Resolving `service` creates only a lightweight proxy bound to `frame`.
Requesting `service.url` evaluates that named definition and follows the fully
qualified `service.host` and `service.port` dependencies. The terminal result
is cached under `service.url`; the proxy owns no independent state.

## Declare intent and use safe fallback

Qualified leaves infer their prefixes. `FRAME_PROXY` is optional low-level
metadata for a Python Module that must promise a scope even when an optional
descendant may be absent; it is not recommended as ordinary configuration-file
layout.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    module = lclang.define_module(
        "optional-service",
        {
            "service": lclang.FRAME_PROXY,
            "service.required": '"ready"',
            "summary": "service?.optional ?? service.required",
        },
    )
    async with lclang.define_frame(module) as frame:
        assert await frame.get("summary") == "ready"
        assert await frame.evaluate("service?.optional ?? 'fallback'") == "fallback"
        assert await frame.evaluate("lhs()") == "<expr>"


asyncio.run(main())
```

The declared `service` prefix is not a real value. Safe access asks the proxy
for `service.optional`; because the complete hierarchy lacks that leaf, it
returns `None` and `??` selects the right side. The unnamed evaluations run in
the Frame but do not add snapshots. Their definition context is `<expr>`.

## Override one leaf and recalculate another

A proxy always starts lookup from the Frame that produced it. A child can
therefore override one scoped leaf while another leaf falls back to its parent.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    timeout = 30

    async def read_timeout() -> int:
        return timeout

    parent = lclang.define_frame(
        lclang.define_module(
            "defaults",
            {"service.timeout": "read_timeout()", "service.retries": "2"},
        ),
        preset={"read_timeout": read_timeout},
    )
    child = parent.derive(
        lclang.define_module("production", {"service.retries": "4"})
    )
    try:
        service = await child.get("service")
        assert await service.timeout == 30
        assert await service.retries == 4
        timeout = 45
        assert await child.get("service.timeout") == 30
        assert await parent.recalculate("service.timeout") == 45
        assert await child.evaluate("service.timeout + service.retries") == 49
    finally:
        await child.close()
        await parent.close()


asyncio.run(main())
```

`service` is bound to the child caller, so terminal traversal checks the child
before the parent. The async host function runs only when `service.timeout` is
first requested. Its `30` snapshot survives the Python variable change until
explicit parent recalculation publishes `45`; the child expression then adds
its local `service.retries` value.

## Reuse named snapshots from an unnamed expression

Each `frame.evaluate` call parses and executes its root expression again.
Named dependencies still use ordinary Frame snapshots.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


async def main() -> None:
    named_calls = 0
    root_calls = 0

    def produce() -> int:
        nonlocal named_calls
        named_calls += 1
        return 21

    def tick() -> int:
        nonlocal root_calls
        root_calls += 1
        return 1

    module = lclang.define_module("calculation", {"scope.value": "produce()"})
    preset = {"produce": produce, "tick": tick}
    async with lclang.define_frame(module, preset=preset) as frame:
        assert await frame.evaluate("scope.value * 2 + tick()") == 43
        assert await frame.evaluate("scope.value * 2 + tick()") == 43
        assert named_calls == 1
        assert root_calls == 2
        closure = await frame.evaluate("() -> lhs()")
        assert await closure() == "<expr>"


asyncio.run(main())
```

The unnamed root calls `tick` on both runs, proving that no root result or
single-flight snapshot is cached. Both calls request the same named
`scope.value`, whose snapshot makes `produce` run once. The returned closure
retains `<expr>` as its lexical `lhs()` owner.

## Configuration and CLI layers

A configuration file may define dotted left-hand names directly. This complete
example also applies a qualified CLI override.

<!-- lclang-tutorial-exec -->
```python
import asyncio
import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.cli import CliContext, CliEntrance, CliResult, CommandGroup, cli


@cli.command()
async def inspect_command(context: CliContext) -> CliResult:
    owner = await context.frame.get("service.owner")
    total = await context.frame.evaluate("int(service.port) + database.pool")
    return CliResult.success(f"{owner}: {total}")


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-scopes-tutorial-") as directory:
        path = Path(directory) / "services.lclcfg"
        path.write_text(
            "# scope: service endpoint\n"
            "service.port: 8000 # Listener port\n"
            "service.owner: lhs() # Full winning key\n"
            "\n"
            "# scope: database capacity\n"
            "database.pool: 4 # Connection count\n",
            encoding="utf-8",
        )
        application = CliEntrance(
            CommandGroup("root", "Scoped inspection", [inspect_command]),
            version="1.0.0",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            status = await application.run(
                [
                    "python",
                    "inspect.py",
                    "inspect",
                    "--config",
                    str(path),
                    "-o",
                    "service.port",
                    "9440",
                ]
            )
        assert status == 0
        assert output.getvalue() == "service.owner: 9444\n"


asyncio.run(main())
```

The qualified leaves infer both prefixes while the standalone comments explain
their purpose. `lhs()` records the full winning key `service.owner`. The CLI
literal wins only for `service.port`; `database.pool` falls back to the config
Frame. The handler's unnamed expression reads both scopes without creating a
new definition, and the application closes all invocation Frames.

The equivalent source is:

```lclcfg
# scope: service endpoint
service.host: "api.example.com" # Deployment DNS name
service.port: 8443 # TLS listener
service.url: f"https://{service.host}:{service.port}" # Complete URL
service.owner: lhs() # Full definition key
```

`service.owner` returns its complete key. CLI applications use the same model:
`-o service.port 9443` supplies a literal scoped override,
`-o service.port "LCL[base_port + 1]"` supplies a lazy definition, and
`-o service LCL[FRAME_PROXY]` still declares an explicit placeholder for APIs
that need one, but normal CLI configuration should supply qualified leaves.

Real values cannot overlap structurally. `service` and `service.port` cannot
both be real, nor can `service.port` and `service.port.value`. Exact overrides
and siblings are valid. Validation runs before mutation or evaluation,
including across a Frame's live hierarchy.

## Handle validation and evaluation failures

Ad hoc evaluation keeps the normal syntax, name, evaluation-limit, and Frame
lifecycle errors. An uncached returned resource belongs to the caller.

<!-- lclang-tutorial-exec -->
```python
import asyncio

import lclang


class Resource:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


async def expect(error_type: type[Exception], operation: object) -> None:
    try:
        await operation
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


async def main() -> None:
    try:
        lclang.define_module("conflict", {"service": "1", "service.port": "2"})
    except ValueError:
        pass
    else:
        raise AssertionError("a real prefix must conflict with its descendant")

    resource = Resource()
    frame = lclang.define_frame(
        lclang.define_module("errors", {"broken": "value()"}),
        preset={"value": 42, "make": lambda: resource},
    )
    await expect(lclang.LclSyntaxError, frame.evaluate("1 +"))
    await expect(lclang.LclNameError, frame.evaluate("missing"))
    await expect(lclang.LclEvaluationError, frame.evaluate("broken"))
    assert await frame.evaluate("make()") is resource
    await frame.close()
    assert resource.closed is False
    await expect(lclang.LclClosedFrameError, frame.evaluate("1"))
    await resource.aclose()
    assert resource.closed is True


asyncio.run(main())
```

The structural conflict fails before a Frame exists. Each invalid unnamed
expression reports its ordinary source-aware error; none becomes an ad hoc
failure snapshot. `broken` is still a named definition, so its own failure uses
normal named caching. The resource returned by `make()` is never stored in the
Frame, so closing the Frame leaves it open for explicit caller cleanup.

## Choose the right boundary

- Use `evaluate` or `evaluate_sync` for one standalone expression and mapping.
- Use `frame.evaluate` for an unnamed expression over an existing context.
- Use `frame.get` for a named definition whose outcome should be cached.

Scoped names never introduce relative lookup: inside `service.url`, `host`
does not mean `service.host`. Explicit paths keep dependencies unambiguous.

[Previous: Production patterns](12-production-patterns.md) | [Next: Tree workflows](14-tree-workflows.md) | [Return to the series introduction](README.md)
