# M060: configuration document model

## Goal

Define the immutable data model for an LCL configuration document before any
text parsing, inclusion, or evaluation is implemented.

## Module and test layout

- Production types live in `pylcl/config/model.py`; public re-exports are
  deferred to M070.
- Behavioural tests live in `tests/config/test_model.py` and reusable builders
  in `tests/config/support.py`.
- Every function, method, and value class, including private helpers, follows
  the full English rST docstring contract. Production files remain under 200
  lines.

## Contract

- `ConfigDocument` is an immutable ordered sequence of declarations associated
  with one `SourceOrigin` and language version.
- A declaration is either `ConfigDefinition` or `ConfigUsing`. Definitions
  contain a validated `Name`, parsed expression, source span, and declaration
  ordinal. Using declarations contain the decoded quoted target, source span,
  and ordinal.
- Construction preserves declaration order and copies caller-owned iterables so
  later mutation cannot affect a document.
- Version metadata defaults to language version 1 and is never a declaration or
  runtime definition. Empty documents are valid. Empty names, non-positive versions, overlapping
  ordinals, mismatched origins, and spans outside their origin raise `ValueError`.
- Duplicate definition names are valid and retain distinct ordinals and spans.
  Models carry syntax and provenance only. They do not read files, resolve
  using targets, expand names, create Frames, or evaluate expressions.

## TDD matrix

- Sunny: construct empty and mixed documents and inspect stable ordered fields.
- Rainy: reject invalid versions, names, origins, spans, and duplicate ordinals.
- Composite-complex: build a document with interleaved definitions and includes,
  mutate all source lists, and prove equality, hashing, and order remain stable.

## Completion evidence

Record the initial failing behavioural command, focused GREEN command, full
`python -m scripts.quality` result, coverage, and date in `progress.md`.
