# M083: fixed-arity argv parser

## Goal

Parse one entrance's argv deterministically into typed values without routing,
configuration loading, help rendering, or handler execution.

## Module and test layout

- Token parsing lives in `pylcl/cli/parser.py`; conversion and parse-result models
  may live in `pylcl/cli/conversion.py` and `pylcl/cli/results.py`.
- Tests live in `tests/cli/test_parser.py`.
- Production modules remain under 200 lines; every callable and value class,
  private or public, has a full English rST docstring.

## Contract

- Positional parameters consume exactly one token each. Options accept
  `--name value`, `--name=value`, or `-x value`; boolean flags consume no value
  and support a declared positive or negative spelling, never implicit bundling.
- `--` ends option recognition. Tokens after it are positional even when they
  begin with `-`. Negative numeric values are accepted where a declared numeric
  converter consumes the next token.
- Options may appear around positionals but each non-repeatable destination may
  occur once. Defaults are applied only after successful parsing.
- Missing/extra positionals, missing option values, unknown options, duplicates,
  invalid conversions, short-option bundles, and ambiguous `--x=y` uses raise
  `CliUsageError` containing token index, spelling, destination, and cause.
- Parsing is pure: it does not mutate argv/models, route commands, load config,
  write errors, evaluate defaults, or invoke handlers.

## TDD matrix

- Sunny: parse every accepted option spelling, flags, negative numerics, defaults,
  and `--` termination.
- Rainy: cover missing, extra, unknown, duplicate, malformed, and conversion
  failures with stable token locations.
- Composite-complex: parse interleaved Unicode positionals/options, aliases,
  negative values, equals syntax, flags, and a post-`--` option-looking token.

## Completion evidence

Record RED/GREEN commands, converter branch coverage, full quality results, and
date in `progress.md`.
