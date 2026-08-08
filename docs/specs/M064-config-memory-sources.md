# M064: in-memory configuration sources

## Goal

Provide a deterministic in-memory parsing boundary with useful synthetic source
identity, without introducing filesystem I/O or include resolution.

## Module and test layout

- The memory-source adapter lives in `pylcl/config/memory.py`.
- Tests live in `tests/config/test_memory.py`; parser cases remain in the M063
  suite rather than being duplicated.
- All production value classes and callables, private or public, follow the full
  English rST docstring contract and the 200-line module limit.

## Contract

- `parse_config(text, *, source_name="<memory>", source_path=None)` accepts Unicode `str` and
  returns a `ConfigDocument`. Bytes are rejected with `TypeError` so decoding
  policy stays at host boundaries.
- `source_name` must be a non-empty display label. Optional `source_path` is
  normalized without reading it and must end in `.lclcfg`.
- In file-backed sources, standalone `__file__` and `__dir__` expression tokens
  become eager string constants for the canonical path and its parent before
  Pratt parsing. Their original spans remain intact and no magic name reaches a
  runtime Module or dependency graph. Pathless use is a structured origin error.
- Every document, declaration, AST, error, and excerpt points to one retained
  `SourceOrigin`; repeated calls return independent immutable graphs.
- The function performs no ambient I/O and is deterministic for equal text and
  source name. Source text is retained only as required by the established
  diagnostic model.
- Using declarations may parse after M065 but cannot be resolved through this
  boundary alone.

## TDD matrix

- Sunny: parse Unicode text with default and custom labels and inspect exact
  origins and spans.
- Rainy: reject bytes, empty labels, malformed headers, and malformed expressions
  without consulting the filesystem.
- Composite-complex: parse equal multiline texts under two labels, prove structural
  equivalence with distinct origins, then verify a nested error cites only its label.

## Completion evidence

Add exact RED, focused GREEN, coverage, full quality, and date evidence to
`progress.md` before marking DONE.
