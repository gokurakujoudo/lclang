# M081: invocation context and host boundaries

## Goal

Represent one CLI invocation explicitly so parsing and execution remain testable,
async-safe, and independent of global process state.

## Module and test layout

- Invocation models and protocols live in `pylcl/cli/context.py`.
- Tests live in `tests/cli/test_context.py`; fake text streams and environments
  live in `tests/cli/support.py`.
- Modules remain under 200 lines and every private/public callable and value
  class has a complete English rST docstring.

## Contract

- `CliContext` snapshots program label, `tuple[str, ...]` argv excluding argv[0],
  Unicode environment mapping, logical working-directory string, stdin reader,
  stdout/stderr writers, and optional cancellation signal.
- `CliContext.from_process()` is the only ambient adapter. Core parsing and run
  functions require a context and never read `sys.argv`, `os.environ`, CWD, or
  global stdio directly.
- Inputs are defensively copied. Environment lookup is host-case-sensitive as
  supplied; no platform-specific folding occurs in the model.
- Stream protocols are async-first and accept/return text. The adapter may wrap
  synchronous standard streams without closing caller-owned streams.
- Invalid argv elements, environment keys/values, blank program labels, and
  unusable streams raise typed construction errors. Cancellation propagates.

## TDD matrix

- Sunny: snapshot fake argv/environment/CWD/streams and perform async writes
  without global state access.
- Rainy: reject non-text or blank fields, writer failures, and cancelled
  operations while retaining their causes.
- Composite-complex: run two contexts concurrently with conflicting argv,
  environments, directories, outputs, and cancellation, proving isolation.

## Completion evidence

Ledger exact RED/GREEN commands, isolation checks, full quality coverage, and
verification date before DONE.
