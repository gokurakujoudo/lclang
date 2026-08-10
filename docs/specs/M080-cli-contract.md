# M080: immutable CLI value contract

## Goal

Define immutable, validated values shared by CLI declaration, parsing, runtime,
logging, and results without inspecting the process or executing user code.

## Module and test layout

- Models live in narrow modules under `pylcl/cli/`; validation helpers may live
  in `pylcl/cli/validation.py`.
- Tests live in `tests/cli/test_models.py` and `tests/cli/test_validation.py`.
- Every production callable and value class, including private ones, uses full
  English rST docstrings, and each source module stays below 200 lines.

## Contract

- `ParameterDoc` stores a valid LCL identifier, display-only type hint, required
  flag, normalized description, and optional default. `None` means no declared
  default and cannot also represent an explicit default value.
- `CliParams` snapshots executable path, routed command tuple, invocation date,
  dryrun flag, optional config path, and read-only raw-string overrides. M097
  additionally permits exact boolean `True` for a valueless override.
- `CliResultStatus` is an `IntEnum`: `SUCCESS=0`, `FAILURE=1`, and
  `EXCEPTION=2`. `CliResult` pairs one status with a Unicode description.
- `LogConfig` defaults to disabled file logging (`log_dir=None`), file name
  `pylcl.log`, level `INFO`, and a percent-style format containing timestamp,
  level, filename, line, function, interpolated message, and raw arguments.
  `CliConfig` owns one immutable `LogConfig`.
- All models defensively detach caller containers and expose tuples or read-only
  mappings. They validate field types, non-empty text, identifiers, dates, log
  levels, leaf log filenames, and required logging-format fields.
- Models contain data only and never inspect argv, stdio, CWD, configuration,
  log files, Frames, handlers, or event loops.

## TDD matrix

- Sunny: construct every model and inspect enum values, defaults, declaration
  order, normalized text, and immutable snapshots.
- Rainy: reject invalid types, identifiers, dates, statuses, log filenames,
  levels, and formats with field-specific messages.
- Composite-complex: mutate all supplied containers after construction and prove
  a Unicode invocation/result/log model graph remains unchanged.

## Completion evidence

Record behavioural RED, focused GREEN, strict typing/doc checks, full quality
coverage, and date in `progress.md`.
