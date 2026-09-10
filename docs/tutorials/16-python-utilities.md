# Python utilities for downstream applications

lclang includes small Python APIs that remain useful when an application does
not evaluate LCL source or use the lclang command-line framework. They keep the
same typed, async-first, explicit-ownership approach without forcing a larger
integration.

## What you will learn

- how to read the live process environment without snapshotting or mutation;
- how to generate Snowflake IDs in Python and reuse the same state in LCL;
- how to create and close an isolated file logger outside `lclang.cli`;
- how to call the reviewed iterable, text, data, and JSON helpers from Python;
- how to reuse business-day calendars in an ordinary async application;
- which package owns each downstream utility surface.

## Read the live environment

Import `env` from `lclang.utils`. Attribute access is convenient for valid
Python and LCL identifiers; `get` also accepts names containing punctuation.
Every access consults `os.environ` at that moment.

<!-- lclang-doc-exec -->
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

## Generate Snowflake IDs

Create one `SnowflakeGenerator` for an application-assigned worker and retain it.
Each synchronous `next_id()` call reads UTC wall-clock milliseconds and allocates
a sequence under a thread lock. No event loop or cleanup scope is needed.
The clock is frozen here only to make the example deterministic.

<!-- lclang-doc-exec -->
```python
from unittest.mock import patch

from lclang.utils import SnowflakeGenerator

ids = SnowflakeGenerator(worker_id=7)
with patch("lclang.utils.snowflake.time_ns", return_value=(ids.epoch_ms + 1) * 1_000_000):
    first = ids.next_id()
    second = ids.next_id()
    assert first == (1 << 22) | (7 << 12)
    assert second == first + 1
```

The first millisecond after the default 2024-01-01 UTC epoch occupies the high
41 bits; worker 7 occupies the next 10, and sequences 0 and 1 occupy the low 12.
The signed 64-bit sign bit stays clear. IDs are predictable identifiers, not
secrets. Different concurrent generators must have distinct worker IDs in
`0..1023` and the same epoch. State is not persisted: before reusing a worker
after restart, ensure time is beyond every timestamp it previously emitted.
Do not inherit generators into forked children or recreate them per ID.

LCL exposes the same constructor as `SnowflakeGenerator`. A retained definition
owns one generator; named ID results follow ordinary Frame snapshot rules.

<!-- lclang-doc-exec -->
```python
import asyncio
from unittest.mock import patch

import lclang


async def main() -> None:
    module = lclang.define_module("request", {
        "ids": "SnowflakeGenerator(worker_id, epoch_ms=0)",
        "request_id": "ids.next_id()",
        "label": 'f"request-{request_id}"',
    })
    with patch("lclang.utils.snowflake.time_ns", return_value=1_000_000):
        async with lclang.define_frame(module, preset={"worker_id": 7}) as frame:
            first = (1 << 22) | (7 << 12)
            assert await frame.get("request_id") == first
            assert await frame.get("request_id") == first
            assert await frame.get("label") == f"request-{first}"
            await frame.recalculate("request_id")
            assert await frame.get("request_id") == first + 1
            assert await frame.get("label") == f"request-{first}"


asyncio.run(main())
```

`request_id` resolves `ids`, which constructs the generator once using the host
worker. The second lookup reuses the cached ID. Recalculation calls the same
generator again, increasing the sequence; the dependent `label` retains its
earlier snapshot. Never recalculate `ids`, because a fresh generator resets the
sequence and may duplicate an ID. Separate Frames needing the same worker
should instead borrow one application-owned Python instance:

<!-- lclang-doc-exec -->
```python
import asyncio
from unittest.mock import patch

import lclang
from lclang.utils import SnowflakeGenerator


async def main() -> None:
    ids = SnowflakeGenerator(7, epoch_ms=0)
    module = lclang.define_module("request", {"id": "ids.next_id()"})
    with patch("lclang.utils.snowflake.time_ns", return_value=1_000_000):
        generated = []
        for _ in range(2):
            async with lclang.define_frame(module, preset={"ids": ids}) as frame:
                generated.append(await frame.get("id"))
        assert generated == [(1 << 22) | (7 << 12), (1 << 22) | (7 << 12) | 1]


asyncio.run(main())
```

Each Frame owns its cached `id` and closes independently. The preset borrows
the same generator, so closing the first Frame does not reset the sequence.
Clock rollback raises `RuntimeError`; a pre-epoch clock raises `ValueError`.
Exhausting 4096 sequences in one millisecond or the 41-bit timestamp raises
`OverflowError`. These failures preserve state and never wait for the clock.
After sequence exhaustion, retry only when time advances. See the
[Snowflake reference](../reference/utilities.md#snowflake-ids) for the full contract.

## Own a standalone logger

A process entry point owns one handler scope. Application loggers only bind
source names and prefixes; the scope owns the background writer and its sinks.

<!-- lclang-doc-exec -->
```python
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.logger import LoggerHandlerConfig, use_logger, use_logger_handler


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-logger-tutorial-") as directory:
        config = LoggerHandlerConfig(
            console={"enabled": False},
            file={"worker": {"directory": directory}},
        )
        async with use_logger_handler(config) as runtime:
            logger = await use_logger(name="example.worker", prefix="[WORKER]")
            logger.info("processed %d records", 3)
        paths = list(Path(directory).glob("*.log"))
        assert len(paths) == 1
        text = paths[0].read_text(encoding="utf-8")
        assert text.startswith("log file: ")
        assert "[WORKER] processed 3 records" in text
        assert runtime.metrics.records_written == 1


asyncio.run(main())
```

The producer enqueues the record without file I/O. Scope exit drains it before
returning, so reading the segment afterwards observes the completed message.
The exclusive filename contains the process ID, UTC creation timestamp, and
sequence. Closed segments keep that path permanently. Console output can run
alongside any number of files. The [logger reference](../reference/logger.md)
explains templates, rotation, filtering, cancellation, and worker initialization.

## Reuse the reviewed standard helpers

The functions behind LCL's `iter`, `text`, `data`, and `json` namespaces are
also direct exports from `lclang.stdlib`. The iterable and join helpers accept
synchronous or asynchronous iteration.

<!-- lclang-doc-exec -->
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

<!-- lclang-doc-exec -->
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

## Render an untrusted representation safely

Use `safe_repr` when a value's display code must not break a diagnostic. Masking
skips rendering entirely, and a canonical renderer can choose the displayed form.

<!-- lclang-doc-exec -->
```python
from lclang.utils import safe_repr

assert safe_repr(42) == "42"
assert safe_repr("private", masked=True) == "*masked*"
assert safe_repr("line", renderer=lambda value: "a\n" + value) == "a\\nline"
assert len(safe_repr("x" * 300)) == 200
assert safe_repr("x" * 300, max_length=None) == repr("x" * 300)
```

The default limit counts characters after line-break escaping and includes the
truncation marker. `None` preserves the full escaped representation. A failed
renderer produces a stable failure description; the helper adds no type label.

## Choose the narrowest public surface

Downstream code can adopt only the layer it needs:

- `lclang.utils` provides the live environment, safe representations, and Snowflake
  IDs; `lclang.logger` owns process logging.
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
