# M090: console entry points and process adapter

## Goal

Connect the context-based CLI runner to installed console scripts without moving
ambient process behaviour into the core implementation.

## Module and test layout

- Process adaptation lives in `pylcl/cli/main.py`; package metadata declares the
  console script only after its application contract is finalized.
- Tests live in `tests/cli/test_main.py` plus isolated installed-script smoke
  tests in the release tooling.
- Every production callable and value class, including private ones, has a full
  English rST docstring; source files remain below 200 lines.

## Contract

- `main(argv: Sequence[str] | None = None) -> int` snapshots a process context,
  runs the sync adapter once, and returns status. Only the generated console
  wrapper turns that return value into process exit status.
- Explicit argv excludes the executable name and enables in-process tests.
  `None` uses `sys.argv[1:]`. Program display name comes from configured
  application metadata rather than an unstable absolute executable path.
- The installed `pylcl` tool exposes language/config inspection built-ins and a
  host API can construct other applications; there is no automatic module,
  entry-point, filesystem, or plugin discovery.
- Expected CLI/config/runtime errors use established renderers. Unexpected
  exceptions are allowed to propagate from `main`; the console wrapper does not
  suppress tracebacks. `KeyboardInterrupt` maps to conventional status 130 after
  best-effort async cleanup.
- Importing `pylcl.cli.main` performs no argv parse, I/O, event-loop creation,
  logging configuration, environment mutation, or process exit.

## TDD matrix

- Sunny: call `main` with explicit argv and run the installed console wrapper,
  checking output and status.
- Rainy: verify unexpected errors propagate, interrupt maps to 130, import is
  inert, and no application/plugin discovery occurs.
- Composite-complex: clean-install the package and invoke help, config-check, and
  dry-run against Unicode paths while separating stdout/stderr and exit statuses.

## Completion evidence

Record RED/GREEN commands, import-side-effect audit, installed smoke output, full
quality coverage, and date in `progress.md`.
