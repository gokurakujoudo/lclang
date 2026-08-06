# M087: async and synchronous CLI execution

## Goal

Orchestrate routing, parsing, binding, handler evaluation, output, exit status,
and cleanup through a stable async-first run boundary.

## Module and test layout

- Execution lives in `pylcl/cli/run.py`; exit/error mapping may live in
  `pylcl/cli/outcomes.py`.
- Tests live in `tests/cli/test_run.py` with fake handlers/streams in support.
- Every production callable and value class, public or private, has a complete
  English rST docstring and source modules stay below 200 lines.

## Contract

- `run_cli(application, context, *, resolver=None, preset=None)` is async and
  returns an integer process status without raising expected usage/help errors.
  `run_cli_sync` is the sole CLI sync adapter and rejects an already-running loop.
- Help/version requests write stdout and return 0. Usage/routing/conversion errors
  write stderr and return 2. Config errors return 3. LCL/handler failures return
  1. Cancellation and `KeyboardInterrupt` are not converted.
- Handlers may be sync Python, async Python, or LCL. `None` means status 0; `int`
  in 0..255 is the status; `str` is written with one trailing newline and status
  0. Other results and invalid integers are handler failures.
- The runner writes diagnostics through context streams, never calls process
  `exit`, and always closes invocation-owned resources before returning/raising.
- Unexpected host bugs retain tracebacks for API callers; an entry-point adapter
  may render them according to M090 policy.

## TDD matrix

- Sunny: execute all handler kinds/results plus help through async and sync
  boundaries with exact output/status.
- Rainy: cover every error class/exit mapping, stream failure, invalid result,
  nested-loop rejection, cancellation, and cleanup.
- Composite-complex: route/load/bind an LCL handler using config, CLI values,
  stdlib and async resources, then verify output, dependencies, status, and close.

## Completion evidence

Record RED/GREEN orchestration tests, exact output/status matrix, full quality
coverage, and date in `progress.md`.
