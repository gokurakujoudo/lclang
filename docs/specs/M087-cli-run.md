# M087: async command execution and result mapping

## Goal

Execute exactly typed async handlers through a no-ordinary-exception boundary,
print/log their results, map statuses, and clean all invocation resources.

## Module and test layout

- Execution lives in `pylcl/cli/run.py`; result rendering and exit mapping may
  live in `pylcl/cli/outcomes.py`.
- Tests live in `tests/cli/test_run.py` with static handlers/configs in support.
- Every production callable and value class, public or private, has a complete
  English rST docstring and source modules stay below 200 lines.

## Contract

- `Command.run(args=None)` and `CliEntrance.run(args=None)` are async and return
  integer statuses. The caller may use `asyncio.run(...)`; the library adds no
  synchronous adapter and never calls process exit.
- Both accept full argv. Direct command run optionally consumes its own name and
  skips group routing; entrance run routes the full nested command path.
- Explicit help/version return 0 on stdout. Missing/unknown commands and usage
  errors return 2 on stderr. A handler must return `CliResult`; any other value is
  an execution exception.
- Print and log each non-empty description exactly once: SUCCESS to stdout/INFO,
  FAILURE to stderr/ERROR, explicit EXCEPTION to stderr/ERROR. The enum value is
  the program status.
- Catch ordinary `Exception`, write a concise description to stderr, call
  `logger.exception` when a logger exists, and return 2. Cancellation,
  `KeyboardInterrupt`, and `SystemExit` propagate after best-effort cleanup.
- Close all Frames and the logger on every path. Cleanup failure upgrades a
  completed SUCCESS/FAILURE to EXCEPTION; with a primary exception, retain its
  description and log cleanup separately.
- Help/version short-circuit before config load, Frame construction, log directory
  creation, logger configuration, required checks, or handler invocation.

## TDD matrix

- Sunny: execute each `CliResultStatus` through direct and routed runs and assert
  exact stdout/stderr, records, integer status, and cleanup.
- Rainy: cover route/parse/config/required/logging/handler/result/output/cleanup
  failures, plus cancellation and process-control propagation.
- Composite-complex: route a nested handler over a static Unicode include graph,
  evaluate lazy values, emit parameterized logs/results, and verify dependency,
  stream, status, traceback, and reverse cleanup behavior.

## Completion evidence

Record RED/GREEN orchestration tests, exact output/status matrix, full quality
coverage, and date in `progress.md`.
