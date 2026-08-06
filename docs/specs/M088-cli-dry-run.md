# M088: side-effect-free dry-run plans

## Goal

Explain what a CLI invocation would select and bind without executing user LCL or
Python handlers.

## Module and test layout

- Planning models and orchestration live in `pylcl/cli/plan.py`.
- Tests live in `tests/cli/test_plan.py`; serialization fixtures stay local to
  the CLI test support boundary.
- Production modules stay under 200 lines and every callable/value class,
  including private ones, has a full English rST docstring.

## Contract

- `plan_cli(...)` performs routing and argv conversion and may parse/load config,
  but does not create a Frame, evaluate config definitions/computed defaults, call
  handlers, acquire LCL context managers, or write output.
- `CliPlan` immutably reports command path, handler kind/target, supplied/defaulted
  parameter spellings, redacted values, config root/version/origins, definition
  names, and resources that execution would own.
- `--dry-run` is a reserved built-in option recognized before entrance parsing.
  It renders canonical UTF-8-safe JSON with sorted object keys and declaration-
  ordered arrays, writes stdout, and returns status 0.
- Parameters marked sensitive are represented as `"<redacted>"` in objects,
  reprs, diagnostics, and JSON. Their actual values remain available only to a
  future real invocation.
- Route, usage, conversion, and config errors retain normal status codes; planning
  must close any loader/resource it created.

## TDD matrix

- Sunny: plan Python/LCL entrances and snapshot deterministic human/model/JSON
  fields without handler calls.
- Rainy: prove sensitive data and side effects never leak, invalid argv/config
  still fail correctly, and temporary resources close.
- Composite-complex: plan a nested command with includes, shadowing, mixed
  supplied/defaulted/sensitive values and a handler that would fail if called.

## Completion evidence

Record RED side-effect sentinels, GREEN model/JSON checks, full quality coverage,
and date in `progress.md`.
