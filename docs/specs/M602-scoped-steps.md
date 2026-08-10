# M602: scoped workflow steps

## Contract

`ExecutionStatusManager.add_step(name, description)` appends a `STEP` in
`RUNNING` state and returns a synchronous context manager for that exact shared
tree node. Clean scope exit changes the step to `SUCCESS` only when it is still
`RUNNING`. A status selected explicitly inside the scope is retained.

Exceptional scope exit replaces the step status with `ERROR`, replaces its
description with `str(exception)`, finalizes the step, and never suppresses the
original exception. Every scope exit locks the step against later handle
updates. Finalizing an ancestor while an unclosed step is still `RUNNING` retains
the M601 rule that unfinished work becomes `FAILURE`.

The existing `add_step(name, description, status)` call remains supported. It
returns the same step handle, initializes the requested status, and need not be
used as a context manager.

## Public interfaces

- Export `ExecutionStatusStep` from `pylcl.workflow`.
- Change `manager.add_step(name, description, status=RUNNING) ->
  ExecutionStatusStep`.
- Add `step.update(description=None, status=None) -> None`. `None` preserves the
  corresponding field, permitting description-only, status-only, and combined
  updates.
- `ExecutionStatusStep` implements synchronous `__enter__`/`__exit__`;
  `__enter__` returns the same handle and `__exit__` returns `Literal[False]`.

## Failure behaviour

- Invalid descriptions or statuses raise `TypeError` before either field changes.
- Entering, updating, or exiting an already-finalized step raises `RuntimeError`.
- An exception in the step scope always wins over a status assigned earlier in
  that scope and remains visible to the caller.

## Test cases

- A two-argument step is visible as `RUNNING` inside its scope and becomes
  `SUCCESS` on clean exit.
- Description-only, status-only, and combined updates mutate the shared node;
  non-running statuses survive clean exit.
- Exceptional exit records `ERROR` plus the exception message and re-raises.
- Invalid atomic updates and every locked-handle operation fail predictably.
- Existing explicit-status step creation and unfinished parent finalization stay
  compatible.
- Tutorial examples execute with the documented statuses and descriptions.

## Acceptance

- RED: focused M602 tests fail against the M601 API.
- GREEN: all workflow tests pass.
- VERIFIED: `venv\Scripts\python.exe -m scripts.quality` and
  `git diff --check` pass.

