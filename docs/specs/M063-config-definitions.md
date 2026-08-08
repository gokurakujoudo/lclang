# M063: configuration versions and definitions

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

- The optional first meaningful declaration is `__LCL_VERSION__: INTEGER`;
  comments and blank lines may precede it, omission selects version 1, and the
  metadata never becomes a definition. M069 enriches its diagnostics.
- A definition is `identifier: expression`. Whitespace around `:` is optional,
  and the right side uses the complete LCL v1 grammar in `docs/lcl-lang.md`.
- Exactly one top-level declaration occupies a logical line. `=` inside calls,
  displays, strings, f-strings, comparisons, or function forms is not mistaken
  for the declaration separator.
- Duplicate definitions are valid and preserved in order for later expansion.
  Empty right sides, invalid names, assignment-like
  chains, and trailing tokens surface as `LclConfigSyntaxError` with adjusted
  document coordinates and the underlying `LclSyntaxError` as cause.
- Every parsed binding name in the LCL grammar rejects the `__` prefix: config
  definitions, function parameters, comprehension targets, exception aliases,
  and context-manager aliases. Non-binding references remain compatible.
- Parsing produces only the immutable M060 model; no ordinary expression is evaluated.

## TDD matrix

- Sunny: parse a header plus scalar, collection, function, and multiline
  definitions and compare their ASTs and spans.
- Rainy: reject late/duplicate/unsupported versions, `=` declarations, empty
  expressions, double-underscore bindings, and malformed LCL with excerpts.
- Composite-complex: parse a comment-heavy document whose RHS contains a nested
  comprehension, f-string, conditional, and keyword argument using internal `=`.

## Completion evidence

Record the RED reproduction, focused GREEN command, full quality gate and its
coverage/date in `progress.md`.
