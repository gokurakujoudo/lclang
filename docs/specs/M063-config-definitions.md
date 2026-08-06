# M063: configuration headers and definitions

## Goal

Parse logical lines into a version header and named LCL definitions with precise
source diagnostics.

## Module and test layout

- Declaration parsing lives in `pylcl/config/parser.py`; small parser state may
  be split into `pylcl/config/parser_state.py`.
- Tests live in `tests/config/test_parser.py` and use the real language parser.
- All production functions, methods, and value classes have full English rST
  docstrings, and every source file remains below 200 lines.

## Contract

- The first meaningful line is exactly `lcl 1`; comments and blank lines may
  precede it. M069 later enriches version diagnostics but does not change syntax.
- A definition is `identifier = expression`. Whitespace around `=` is optional,
  and the right side uses the complete LCL v1 grammar in `docs/lcl-lang.md`.
- Exactly one top-level declaration occupies a logical line. `=` inside calls,
  displays, strings, f-strings, comparisons, or function forms is not mistaken
  for the declaration separator.
- Duplicate definitions in one document are rejected at the later name and cite
  the original declaration. Empty right sides, invalid names, assignment-like
  chains, and trailing tokens surface as `LclConfigSyntaxError` with adjusted
  document coordinates and the underlying `LclSyntaxError` as cause.
- Parsing produces only the immutable M060 model; no expression is evaluated.

## TDD matrix

- Sunny: parse a header plus scalar, collection, function, and multiline
  definitions and compare their ASTs and spans.
- Rainy: reject missing headers, duplicate names, empty expressions, chained
  assignment, and malformed LCL with source excerpts.
- Composite-complex: parse a comment-heavy document whose RHS contains a nested
  comprehension, f-string, conditional, and keyword argument using internal `=`.

## Completion evidence

Record the RED reproduction, focused GREEN command, full quality gate and its
coverage/date in `progress.md`.
