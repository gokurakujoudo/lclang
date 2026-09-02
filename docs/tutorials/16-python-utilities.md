# Python utilities for downstream applications

lclang includes small Python APIs that remain useful when an application does
not evaluate LCL source or use the lclang command-line framework. They keep the
same typed, async-first, explicit-ownership approach without forcing a larger
integration.

## What you will learn

- how to read the live process environment without snapshotting or mutation;
- how to create and close an isolated file logger outside `lclang.cli`;
- how to call the reviewed iterable, text, data, and JSON helpers from Python;
- how to reuse business-day calendars in an ordinary async application;
- which package owns each downstream utility surface.

## Read the live environment

Import `env` from `lclang.utils`. Attribute access is convenient for valid
Python and LCL identifiers; `get` also accepts names containing punctuation.
Every access consults `os.environ` at that moment.

<!-- lclang-tutorial-exec -->
```python
import os
from unittest.mock import patch

from lclang.utils import Environment, env


with patch.dict(os.environ, {"LCLANG_REGION": "blue"}, clear=False):
    assert isinstance(env, Environment)
    assert env.LCLANG_REGION == "blue"

    os.environ["LCLANG_REGION"] = "green"
    assert env.LCLANG_REGION == "green"
    assert env.get("deployment-region", "local") == "local"
    assert "LCLANG_REGION" in env.field_names()
```

The singleton is a live read-only view, not a Frame proxy. Assigning to or
deleting `os.environ` remains the host application's responsibility. In an LCL
Frame, the canonical `env` binding adds scoped configuration overrides above
the same live fallback without mutating the process environment.

## Own a standalone logger

`LogConfig` and `create_logger` do not require a CLI entrance. The returned
`LoggerHandle` owns its handlers, so close it when the application component is
finished.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.utils import LogConfig, create_logger


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-logger-tutorial-") as directory:
        root = Path(directory)
        handle = await create_logger(
            LogConfig(
                log_dir=str(root),
                log_file_name="worker.log",
                log_level="INFO",
            ),
            "example.worker",
        )
        try:
            handle.logger.info("processed %d records", 3)
            assert handle.log_path == root / "worker.log"
        finally:
            handle.close()

        text = (root / "worker.log").read_text(encoding="utf-8")
        assert "INFO" in text
        assert "processed 3 records" in text


asyncio.run(main())
```

The factory creates a non-propagating standard-library logger. It creates the
directory and UTF-8 file only when logging is enabled; `LogConfig()` instead
uses a null handler. `close()` is idempotent, which makes cleanup safe in a
`finally` block. `DEFAULT_LOG_FORMAT` is public when an application wants to
extend the default while retaining its diagnostic fields.

## Reuse the reviewed standard helpers

The functions behind LCL's `iter`, `text`, `data`, and `json` namespaces are
also direct exports from `lclang.stdlib`. The iterable and join helpers accept
synchronous or asynchronous iteration.

<!-- lclang-tutorial-exec -->
```python
import asyncio

from lclang.stdlib import collect, first, join, json_decode, json_encode, lookup, merge


async def labels():
    for label in ("blue", "green"):
        yield label


async def main() -> None:
    assert await collect(labels()) == ["blue", "green"]
    assert await first([], "missing") == "missing"
    assert await join(" / ", labels()) == "blue / green"

    settings = merge({"retries": 2, "region": "blue"}, {"region": "green"})
    assert lookup(settings, "region") == "green"
    assert lookup(settings, "timeout", 30) == 30

    payload = json_encode({"regions": ["blue", "green"]})
    assert payload == '{"regions":["blue","green"]}'
    assert json_decode(payload) == {"regions": ["blue", "green"]}


asyncio.run(main())
```

`merge` is a shallow, left-to-right operation returning a read-only mapping.
The JSON helpers reject nonstandard `NaN` and infinity rather than emitting
implementation-specific data. Other public exports include `lines`, the
fixed-point `recursive` helper, and the manifest APIs used to assemble a
reviewed standard preset.

## Use calendars in ordinary async code

Calendars live under `lclang.utils.calendar` and do not depend on parsing LCL.
This example turns a weekend report date into the next weekday and then moves
one further business day.

<!-- lclang-tutorial-exec -->
```python
import asyncio
from datetime import date

from lclang.utils.calendar import ALL_DAYS, ALL_WEEKDAYS


async def main() -> None:
    report_day = ALL_DAYS.map_this_or_next(ALL_WEEKDAYS)
    settlement_day = report_day.shift_n_days(1, ALL_WEEKDAYS)

    saturday = date(2024, 1, 6)
    assert await report_day.map_date(saturday) == date(2024, 1, 8)
    assert await settlement_day.map_date(saturday) == date(2024, 1, 9)


asyncio.run(main())
```

The first mapping adjusts Saturday to Monday. The chained shift begins from
that mapped value and reaches Tuesday. For calendar algebra, sparse policies,
strict JSON loading, and managed caches, continue with the
[business-day calendar chapter](11-business-day-calendars.md).

## Choose the narrowest public surface

Downstream code can adopt only the layer it needs:

- `lclang.utils` provides the live environment and standalone logging.
- `lclang.stdlib` provides reviewed pure-data helpers and preset assembly.
- `lclang.utils.calendar` provides date policy and managed calendar loading.
- `lclang.workflow` provides typed task trees and nested execution status.
- `lclang.cli` provides command discovery, binding, auditing, and process exit
  behavior.

The latter two are larger application frameworks, covered by the
[tree-workflow](14-tree-workflows.md) and
[command-line application](09-command-line-applications.md) chapters. None is
required merely to use `env`, create a logger, transform reviewed data, or
apply a calendar.

For the complete stable names and contracts, see the
[utilities reference](../reference/utilities.md). Keep imports at the owning
public package instead of reaching into implementation modules; that leaves
each application explicit about the subsystem and lifecycle it has adopted.

[Previous: Case Study: Energy Settlement Workflow](15-energy-settlement-workflow.md) | [Return to the series introduction](README.md)
