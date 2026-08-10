# M083: full-argv and common-option parser

## Goal

Parse the executable/script boundary and one routed command's fixed common
options into immutable `CliParams` without configuration or evaluation.

## Module and test layout

- Token parsing lives in `pylcl/cli/parser.py`; override classification may live
  in a focused sibling module.
- Tests live in `tests/cli/test_parser.py`.
- Production modules remain under 200 lines; every callable and value class,
  private or public, has a full English rST docstring.

## Contract

- Explicit input is full argv `[python_executable, script.py, ...]`; `None` is
  adapted elsewhere to `[sys.executable, *sys.argv]`. Require non-empty text
  tokens and an exact `.py` script suffix. Preserve the executable token exactly;
  the script is retained only for rendering.
- After a routed command, accept only `-c/--config FILE`, repeatable
  `-o/--override KEY [VALUE]`, `-a/--as-of YYYYMMDD`, `-wif/--dryrun`, and
  `-h/--help`. Use separate tokens only; do not accept positionals, bundles,
  equals syntax, or `--` termination.
- Config, as-of, and dryrun occur at most once. Repeated override keys are
  right-biased. Under the M097 refinement, an omitted value becomes `True` and
  `-o`/`--override` always starts the next override; all other dash-prefixed
  tokens remain values when consumed by the optional value slot.
- Override keys must be valid LCL identifiers and cannot be `as_of_date`,
  `dryrun`, or `cli_params`. Dates use strict `YYYYMMDD`; omission captures one
  local execution date.
- A whole `LCL[...]` value becomes a deferred expression only when the non-empty
  body parses successfully. Empty/malformed markers and partial shapes remain
  literal strings.
- Failures raise `LclCliUsageError` with token index and spelling. Parsing is pure:
  no routing, I/O, config load, Frame/logger creation, output, or evaluation.

## TDD matrix

- Sunny: parse every alias, omitted/explicit date, Unicode config path, repeated
  distinct overrides, dryrun, and help.
- Rainy: cover short argv, non-`.py` script, missing arity, unknown/bare tokens,
  duplicate singleton flags, invalid dates/keys, and reserved overrides.
- Composite-complex: parse mixed aliases with duplicate last-wins keys, dash-like
  values, valid nested-bracket LCL, and malformed markers that stay literal.

## Completion evidence

Record RED/GREEN commands, converter branch coverage, full quality results, and
date in `progress.md`.
