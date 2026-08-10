# M090: Python-script process adapter

## Goal

Adapt ambient Python-script argv to the async entrance without adding a console
entry point or moving process exit into the library.

## Module and test layout

- Ambient argv adaptation lives in `pylcl/cli/process.py`; run methods retain
  orchestration ownership.
- Tests live in `tests/cli/test_process.py` plus isolated sample-script smoke tests.
- Every production callable and value class, including private ones, has a full
  English rST docstring; source files remain below 200 lines.

## Contract

- Explicit `run(args)` requires full argv including Python executable and `.py`
  script. `run(None)` snapshots `[sys.executable, *sys.argv]` exactly once.
- `CliParams.executable_path` preserves the supplied executable token. Script
  path is not public params state; its basename labels usage/version output.
- Application scripts call `asyncio.run(cli_entrance.run())` or
  `asyncio.run(cli_entrance.run(full_args))` and return/use the integer result.
- Importing `pylcl.cli` performs no argv parse, I/O, event-loop creation, logging
  setup, environment mutation, process exit, filesystem/application/plugin
  discovery, or handler execution.
- The package adds no `[project.scripts]` entry and no synchronous CLI adapter.

## TDD matrix

- Sunny: call explicit and ambient paths from a sample `.py` application and
  assert captured executable, display label, output, and status.
- Rainy: reject incomplete/non-text/non-`.py` argv; prove imports are inert and
  process-control exceptions remain visible.
- Composite-complex: clean-install and invoke a spaced Unicode sample-script path
  directly through Python using token arrays, static config, and temporary logs.

## Completion evidence

Record RED/GREEN commands, import-side-effect audit, installed smoke output, full
quality coverage, and date in `progress.md`.
