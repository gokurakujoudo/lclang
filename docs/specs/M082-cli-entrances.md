# M082: entrance declaration and callable binding

## Goal

Provide explicit builders/decorators that turn typed Python callables or LCL
targets into M080 entrances without executing them.

## Module and test layout

- Declaration helpers live in `pylcl/cli/entrances.py`; Python signature mapping
  may be split into `pylcl/cli/signatures.py`.
- Tests live in `tests/cli/test_entrances.py`.
- Every production callable/value class, public or private, follows the complete
  English rST docstring contract; modules stay below 200 lines.

## Contract

- `entrance(...)` records metadata on a callable without mutating its signature;
  `CliApplicationBuilder.add(...)` converts declarations into immutable models.
- Supported signature inference is deliberately narrow: positional parameters,
  keyword-only options, `str`/`int`/`float`/`bool` annotations, optional defaults,
  and async or sync callables. Unannotated, variadic, positional-only, union,
  container, and unsupported annotations require explicit `CliParameter` models.
- Explicit declarations always win over inferred help/metavar/converter but must
  remain compatible with the callable signature.
- LCL handler targets are declared by configuration name/expression and use an
  explicit parameter list; Python reflection is never attempted for them.
- Decoration/building performs no handler call, import discovery, config load,
  event-loop creation, or stdout write. Reusing a callable in two builders creates
  independent metadata.

## TDD matrix

- Sunny: infer a typed sync and async callable and explicitly declare an LCL
  entrance.
- Rainy: reject unsupported signatures, conflicting explicit metadata, duplicate
  decorators, and missing handler targets.
- Composite-complex: combine inferred and explicit parameters across nested
  entrances, defaults, aliases, and two independent applications.

## Completion evidence

Record signature RED cases, focused GREEN suite, strict mypy/doc checks, full
quality coverage, and date in `progress.md`.
