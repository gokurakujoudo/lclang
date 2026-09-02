# Configuration files

A `.lclcfg` file moves trusted definitions out of Python while keeping them
parsed, source-aware, and convertible to the same Module/Frame runtime. Loading
never evaluates a definition.

## What you will learn

- the version, definition, comment, and continuation syntax;
- how `using` expands files in source order;
- how an f-string `using` target selects a file from prior values or `env`;
- how later definitions win while complete history remains available;
- how to group and comment configuration definitions for readers;
- when to use `evaluate_config` or a reusable Frame factory.

## Parse in-memory text

Use `parse_config` when another system already owns the text. It performs no
file access and leaves `using` declarations unresolved.

<!-- lclang-tutorial-exec -->
```python
from lclang.config import parse_config

document = parse_config(
    "__LCL_VERSION__: 1\n"
    "# Derived values remain expressions.\n"
    "subtotal: unit_price * quantity\n"
    "total: subtotal + \\\n"
    "  shipping\n",
    source_name="generated pricing",
)

assert document.version == 1
assert len(document.declarations) == 2
assert str(document.origin.name) == "generated pricing"
```

The metadata selects version 1 and is not counted as a definition declaration.
The parser therefore records exactly `subtotal` and the continued `total`
expression. Because the caller supplied `source_name`, diagnostics identify the
document as `generated pricing` without requiring a file.

A definition uses `name: expression`; `=` is not a separator. A backslash is
the only physical-line continuation marker. Open brackets alone do not continue
a definition. Version metadata may appear only as the first meaningful
declaration.

## Lay out definitions for readers

Keep qualified names from one scope together without blank lines, then use a
blank line before the next scope or functional group. Put a short inline `#`
comment on definitions that need explanation and a standalone `# Section` or
`# scope: <description>` line above each group. Qualified leaves infer their
prefixes, so ordinary files should omit `scope: FRAME_PROXY`.

```lclcfg
# scope: service endpoint
service.host: "api.example.com" # Deployment DNS name
service.port: 8443 # TLS listener

# Retry policy
retry.count: 3 # Maximum attempts
retry.delay: 0.5 # Seconds between attempts
```

`FRAME_PROXY` remains valid when an API deliberately needs an explicit
placeholder, but it adds no value to the usual file layout above.

## Compose files and evaluate final winners

The next example writes an isolated two-file configuration. `using` inserts the
shared definitions at its exact position. The later `discount_rate` overrides
the shared value without losing its history.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.config import evaluate_config, load_config


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-config-tutorial-") as directory:
        root = Path(directory)
        (root / "shared.lclcfg").write_text(
            "# Shared pricing\n"
            "discount_rate: 0.05 # Base discount\n"
            "shipping: 8 # Flat shipping charge\n"
            "currency: 'USD' # Display currency\n",
            encoding="utf-8",
        )
        application = root / "application.lclcfg"
        application.write_text(
            "# Shared definitions\n"
            'using "shared.lclcfg" # Expand at this source position\n'
            "discount_rate: 0.10 # Application discount\n"
            "\n"
            "# Calculated totals\n"
            "subtotal: unit_price * quantity # Before discount\n"
            "total: subtotal * (1 - discount_rate) + shipping # Final charge\n"
            'label: f"{currency} {total:.2f}" # Display text\n',
            encoding="utf-8",
        )

        config = await load_config(application)
        assert tuple(config.definitions) == (
            "discount_rate",
            "shipping",
            "currency",
            "subtotal",
            "total",
            "label",
        )
        assert len(config.history["discount_rate"]) == 2
        assert await evaluate_config(
            config,
            "label",
            values={"unit_price": 25, "quantity": 4},
        ) == "USD 98.00"


asyncio.run(main())
```

Expansion first contributes the shared `0.05` rate, shipping, and currency.
The root's later `0.10` rate becomes the winner while both occurrences remain
in history. With a `100` subtotal, the winning rate leaves `90`; adding `8`
shipping gives `98`, which `label` formats as `USD 98.00`.

Expansion is recursive and deterministic. Relative targets resolve from the
importing file, not the process working directory. Direct and indirect cycles
raise structured configuration errors.

## Select a file from earlier LCL values

A `using` target may be an LCL f-string. Its fields can evaluate definitions
that appeared earlier in source order, including definitions derived from
other earlier values.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.config import evaluate_config, load_config


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-dynamic-using-") as directory:
        root = Path(directory)
        profiles = root / "profiles"
        profiles.mkdir()
        (profiles / "production.lclcfg").write_text(
            'endpoint: "https://api.example.com"\n',
            encoding="utf-8",
        )
        (profiles / "development.lclcfg").write_text(
            'endpoint: "http://localhost:8000"\n',
            encoding="utf-8",
        )
        application = root / "application.lclcfg"
        application.write_text(
            'region: "eu"\n'
            'profile: "production" if region == "eu" else "development"\n'
            'using f"profiles/{profile}.lclcfg"\n'
            'summary: f"{profile}: {endpoint}"\n',
            encoding="utf-8",
        )

        config = await load_config(application)
        assert await evaluate_config(config, "summary") == (
            "production: https://api.example.com"
        )


asyncio.run(main())
```

The loader evaluates `profile` only to select `production.lclcfg`. That work
uses a temporary Frame and does not warm the final configuration's runtime
cache. `endpoint` is inserted at the `using` line, and the later `summary`
definition resolves it normally when requested.

This lookup is deliberately position-sensitive. Moving `profile` below the
`using` line would make the target fail with `LclConfigUsingError`, even though
ordinary final configuration definitions may refer forward.

## Select a file from the live environment

The canonical `env` utility is also available to a dynamic target. Null
coalescing supplies a deterministic fallback, while a loader override can
select a different file without changing `os.environ`.

<!-- lclang-tutorial-exec -->
```python
import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lclang.config import evaluate_config, load_config


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-env-using-") as directory:
        root = Path(directory)
        for profile in ("local", "blue", "green"):
            (root / f"{profile}.lclcfg").write_text(
                f'selected: "{profile}"\n',
                encoding="utf-8",
            )
        application = root / "application.lclcfg"
        application.write_text(
            'using f"{env.LCLANG_TUTORIAL_PROFILE ?? \'local\'}.lclcfg"\n',
            encoding="utf-8",
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LCLANG_TUTORIAL_PROFILE", None)
            local = await load_config(application)
            assert await evaluate_config(local, "selected") == "local"

            with patch.dict(
                os.environ,
                {"LCLANG_TUTORIAL_PROFILE": "blue"},
            ):
                blue = await load_config(application)
                assert await evaluate_config(blue, "selected") == "blue"

                green = await load_config(
                    application,
                    overrides={"env.LCLANG_TUTORIAL_PROFILE": "green"},
                )
                assert await evaluate_config(green, "selected") == "green"
                assert os.environ["LCLANG_TUTORIAL_PROFILE"] == "blue"


asyncio.run(main())
```

With no process value, `??` chooses `local.lclcfg`. The live value then chooses
`blue.lclcfg`. Finally, the call-level scoped override wins only for loading
and selects `green.lclcfg`; the process environment remains `blue`. Overrides
may also be parsed LCL AST values when the selection itself should stay lazy.

Each dynamic target sees prior expanded definitions, call-level overrides, and
canonical builtins. It cannot see later declarations, command defaults, or CLI
runtime-only values. The evaluated result must be non-empty text ending exactly
in `.lclcfg`.

## Share one loaded policy across several runs

Use `evaluate_config` for one result. Use `config.frame_factory()` when several
lookups in one run should share snapshots or when many runs share the same
loaded configuration.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.config import load_config


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-factory-tutorial-") as directory:
        path = Path(directory) / "policy.lclcfg"
        path.write_text(
            "subtotal: price * quantity\n"
            "large: subtotal >= threshold\n",
            encoding="utf-8",
        )
        config = await load_config(path)
        factory = config.frame_factory()

        async with factory.create(
            values={"price": 10, "quantity": 3, "threshold": 50}
        ) as small:
            assert await small.get("subtotal") == 30
            assert await small.get("large") is False

        async with factory.create(
            values={"price": 10, "quantity": 8, "threshold": 50}
        ) as large:
            assert await large.get("subtotal") == 80
            assert await large.get("large") is True


asyncio.run(main())
```

Both Frames use the same parsed definitions and threshold. The first multiplies
`10 * 3` and compares `30 >= 50`, while the second multiplies `10 * 8` and
compares `80 >= 50`. Fresh Frame caches keep the false and true results
independent.

File-backed AST nodes retain their physical source spans. `__file__` and
`__dir__` become eager path constants in file-backed definitions. Apply
`ConfigLoadLimits` and an allowed-root resolver policy when the application
needs bounded, controlled loading.

[Previous: The LCL language](03-language.md) | [Next: Async Python integration](05-async-python-integration.md)
