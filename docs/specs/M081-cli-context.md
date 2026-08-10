# M081: invocation context and logging boundaries

## Goal

Represent the handler-visible state of one invocation and configure an isolated
standard-library logger without mutating the root logger.

## Module and test layout

- Invocation state lives in `pylcl/cli/context.py`; logging construction and
  cleanup live in `pylcl/cli/logging.py`.
- Tests mirror both modules under `tests/cli/`.
- Modules remain under 200 lines and every private/public callable and value
  class has a complete English rST docstring.

## Contract

- `CliContext` exposes `as_of_date`, `dryrun`, the top invocation `Frame`, one
  `logging.Logger`, and the same immutable `CliParams` as `raw_params`.
- Context construction retains Frame and logger references without copying or
  closing them. The runner owns their lifecycle.
- Effective logging values are lazily resolved from final Frame names
  `log_dir`, `log_file_name`, `log_level`, and `log_format`. Configuration and
  CLI overrides may replace the `CliConfig` defaults.
- `log_dir=None` installs no output handler. An enabled logger creates its
  directory relative to CWD, appends UTF-8 to a leaf filename, does not
  propagate, and closes its handler after the invocation.
- Formats use `logging.Formatter` percent fields and must retain time, file,
  line, function, message, and raw arguments. `logger.exception` appends the
  traceback and preserves interpolated call arguments.
- Unit tests use per-case static configuration fixtures. Every enabled log path
  is under a separate automatically cleaned temporary directory.

## TDD matrix

- Sunny: build a context with disabled and enabled loggers, write ordinary and
  exception records, and verify exact fields and cleanup.
- Rainy: reject invalid effective log values, missing format fields, directory
  and file failures, and use after logger closure while preserving causes.
- Composite-complex: run two contexts concurrently with different Frames and
  temporary log roots, proving handler state, records, and cleanup are isolated.

## Completion evidence

Ledger exact RED/GREEN commands, isolation checks, full quality coverage, and
verification date before DONE.
