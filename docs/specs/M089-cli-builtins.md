# M089: CLI built-in commands and options

## Goal

Provide a small, collision-safe set of inspection operations shared by all CLI
applications.

## Module and test layout

- Built-in declaration and dispatch live in `pylcl/cli/builtins.py`.
- Tests live in `tests/cli/test_builtins.py` and reuse canonical help/plan
  renderers rather than snapshotting alternate implementations.
- All production callables/value classes, private or public, use complete English
  rST docstrings and each source module remains under 200 lines.

## Contract

- Default built-ins are root `--help`, command `--help`, root `--version`,
  `config-check`, and global `--dry-run`. Applications may disable individual
  built-ins explicitly but may not silently replace their spellings.
- `config-check` loads/parses/merges the selected configuration, constructs no
  Frame, evaluates no definition, writes `configuration valid\n`, and returns 0.
  Configuration failures use the normal rendered diagnostic and status 3.
- Help/version do not load configuration or initialize handlers. Dry-run follows
  M088. Built-ins are recognized only in documented positions so an argument
  after `--` remains user data.
- Built-in metadata participates in construction collision validation and help
  output. Disabled built-ins disappear from both recognition and documentation.
- Built-ins use only the supplied `CliContext` and host resolver; no process exit,
  ambient I/O, environment mutation, or plugin discovery occurs.

## TDD matrix

- Sunny: invoke each root/command built-in, verify short-circuit scope, output,
  status, and help visibility.
- Rainy: reject collisions, respect disabled built-ins/`--`, and map invalid
  configuration without evaluating definitions.
- Composite-complex: exercise nested command help, a Unicode include graph
  `config-check`, disabled version, and dry-run in one application with call spies.

## Completion evidence

Ledger RED/GREEN commands, short-circuit/side-effect assertions, full quality
coverage, and verification date.
