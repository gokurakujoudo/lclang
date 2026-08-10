# Learn pylcl

This is the shortest path from a Python project to a working LCL-backed value.
You need Python 3.14 or newer. pylcl has no third-party runtime dependencies.

> pylcl evaluates trusted application configuration. It is not a sandbox for
> expressions supplied by an attacker.

## Install

For a checked-out source tree, install the package into the active environment:

```console
python -m pip install .
```

You can also install a verified wheel directly:

```console
python -m pip install ./dist/pylcl-0.3.0-py3-none-any.whl
```

The 0.3.0 release candidate is verified with Python 3.14. It has no third-party
runtime dependencies. Publication is a separate maintainer action, so install
the locally built wheel or source tree until a package index release exists.
Confirm the environment with:

```console
python -c "import pylcl; print(pylcl.__version__)"
```

## Three-minute tour

An LCL **Module** is an immutable collection of named expressions. A **Frame**
evaluates those expressions lazily and caches the results. Definitions can
refer to each other in any order.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def main() -> None:
    module = pylcl.define_module(
        "welcome",
        {
            "greeting": 'f"Hello, {name}!"',
            "excited": "greeting + ' Welcome to pylcl.'",
        },
    )
    frame = pylcl.define_frame(module, preset={"name": "Ada"})
    try:
        assert await frame.get("excited") == "Hello, Ada! Welcome to pylcl."
        assert await frame.get("greeting") == "Hello, Ada!"
    finally:
        await frame.close()


asyncio.run(main())
```

What happened:

1. `define_module` parsed two LCL expressions without evaluating either one.
2. `define_frame` supplied the host value `name` and created an independent
   runtime cache.
3. Asking for `excited` first evaluated its dependency `greeting`.
4. The second lookup returned the cached `greeting` snapshot.
5. `close()` deterministically released work and cached resources owned by the
   Frame.

Most pylcl applications follow that same shape: define or load a Module, create
a Frame for one run, ask for values, and close the Frame in `finally`.

## Tutorials

Read these in order, or jump directly to the job at hand:

1. [Runtime: Modules and Frames](runtime.md) — build modules, supply Python
   values, understand lazy caching, derive Frames, inspect dependencies, and
   clean up safely.
2. [LCL examples gallery](lcl_examples.md) — learn the whole expression
   language from literals through comprehensions, control forms, builtin
   recursion, fixed-point combinators, Fibonacci, and quicksort.
3. [Configuration files](config_file.md) — write `.lclcfg` files, compose them
   with `using`, load them asynchronously, and integrate them into an
   application.
4. [Dependency analytics](dependency-analytics.md) — inspect static references,
   Module and Frame graphs, runtime traces, reconciliation, and safe ordering.
5. [Build a CLI in a Python script](cli.md) — declare typed async commands,
   compose command groups, layer config and overrides, handle dryrun, and log.

6. [Track workflow execution status](workflow-status.md) — collect nested task
   and step outcomes, propagate failures, and finalize sub-tasks with `with`.

## References

- [Complete LCL V1 syntax](../lcl-lang.md)
- [Runtime API guide](../reference/runtime-api.md)
- [Detailed `.lclcfg` reference](../configuration.md)
- [Project status and verification evidence](../../progress.md)

The tutorials cover implemented behavior only.
