# lclang documentation

A typed, async-first configuration expression language for Python. Define
relationships once, supply the context, and calculate only what you need.

- [Quick start](quick-start.md) — Install lclang and make your first calculation.
- [Tutorial series](tutorials/README.md) — Learn through complete, executable examples.
- [Language & API reference](reference/README.md) — Look up syntax, APIs, and lifecycle contracts.
- [Development guide](development/README.md) — Work on the library and run its quality checks.

## Start with one expression

Requires Python 3.14 or newer. Pure Python, with no third-party runtime dependencies.
See [installation](installation.md) for environment setup.

```console
python -m pip install lclang
```

<!-- lclang-doc-exec -->
```python
import lclang

total = lclang.evaluate_sync(
    "unit_price * quantity",
    {"unit_price": 6, "quantity": 4},
)
assert total == 24
```

Python supplies `unit_price` and `quantity`; LCL owns their relationship. The
expression multiplies 6 by 4 and returns 24. In an async application, use
`await evaluate()` or an async Frame instead of `evaluate_sync()`.

## Define once. Evaluate in context.

A **Module** is an immutable collection of named definitions. A **Frame** combines
those definitions with inputs, lazy cached results, and owned asynchronous work
for one run. Reuse the Module; create and close a Frame for each independent run.

```text
Module + host inputs → Frame → requested result
                         └── cached dependency snapshots
```

Names resolve on demand. Concurrent readers share in-flight work, and later
reads reuse the snapshot. Changing an input does not automatically invalidate
its dependants. The [Modules and Frames tutorial](tutorials/02-modules-and-frames.md)
walks through this model with runnable Python.

## Find your next topic

- [Reference index](reference/README.md)
- [LCL V1 language specification](reference/language.md), including immutable records
- [Runtime API](reference/runtime.md), including Frame proxy discovery and records
- [Configuration format and API](reference/configuration.md)
- [Environment, logging, standard, and workflow utilities](reference/utilities.md)
- [Command-line API](reference/cli.md)
- [Tree workflow API](reference/workflow.md)
- [Business-day calendars](reference/calendar.md)
- [Unified process logging](reference/logger.md)

## Trust and ownership

lclang is a trusted configuration language, not a hostile-code sandbox.
Host objects and callables retain the capabilities your application gives them.
Keep that boundary narrow, and close caller-owned Frames with `async with`.

These pages are built from the tested Markdown in `docs/`. The
[GitHub Wiki](https://github.com/gokurakujoudo/lclang/wiki) remains an alternative
view of the same documentation.
