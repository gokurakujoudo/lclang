# M080: typed CLI application contract

## Goal

Define immutable, validated models for command-line applications and entrances
without parsing arguments, loading configuration, or invoking user code.

## Module and test layout

- Models live in `pylcl/cli/model.py`; validation helpers may live in
  `pylcl/cli/validation.py`.
- Tests live in `tests/cli/test_model.py`; reusable builders live in
  `tests/cli/support.py`.
- Every production callable and value class, including private ones, uses full
  English rST docstrings, and each source module stays below 200 lines.

## Contract

- `CliApplication` contains program name, summary, version text, ordered root
  entrances, and built-in policy. `CliEntrance` contains a non-empty command
  path, summary, ordered parameters, and an LCL handler expression/name.
- `CliParameter` declares destination name, positional/option spelling, arity,
  required/default state, converter, metavar, and help. Models defensively copy
  caller iterables and expose immutable tuples/mappings.
- Command and option spellings use portable ASCII rules: command segments match
  `[a-z][a-z0-9-]*`; long options match `--[a-z][a-z0-9-]*`; optional short
  aliases are one ASCII alphanumeric after `-`.
- Duplicate command paths, destinations, or option spellings; prefix-conflicting
  paths without an explicit parent entrance; invalid defaults; and reserved
  built-in names raise `ValueError` at construction.
- Models contain declarative data only and never inspect ambient argv, stdio,
  environment, working directory, config files, or event loops.

## TDD matrix

- Sunny: construct a multi-command application and inspect stable equality,
  hashing, declaration order, and immutable fields.
- Rainy: reject every invalid spelling, collision, prefix ambiguity, default, and
  reserved-name conflict with useful field-specific messages.
- Composite-complex: construct nested commands with mixed positional/options,
  mutate every input container, and prove the validated graph is unchanged.

## Completion evidence

Record behavioural RED, focused GREEN, strict typing/doc checks, full quality
coverage, and date in `progress.md`.
