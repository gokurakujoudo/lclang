# M069: configuration versions and diagnostics

## Goal

Finalize version negotiation and a stable, source-rich configuration error
taxonomy across parsing, resolution, merging, and loading.

## Module and test layout

- Error types live in `pylcl/config/errors.py`; version validation stays in the
  parser boundary and rendering helpers in `pylcl/config/diagnostics.py`.
- Tests live in `tests/config/test_errors.py` and
  `tests/config/test_diagnostics.py`.
- All production callables and value classes, public and private, use complete
  English rST docstrings; modules remain below 200 lines.

## Contract

- Every source requires one first meaningful `lcl INTEGER` header. Version `1`
  is supported; missing, duplicate, non-integer, zero/negative, and unsupported
  versions are distinct configuration errors.
- Each included document negotiates independently. An unsupported child cannot
  inherit the root version or be silently skipped.
- Public subclasses cover syntax, version, include, cycle, merge, and lifecycle
  failures under `LclConfigError`. Each carries a stable machine code, message,
  primary origin/span, ordered related locations, and original cause when present.
- Human rendering includes display name, one-based line/column, source excerpt,
  caret, and an outermost-to-innermost include trace. Rendering is deterministic,
  newline-neutral, Unicode-safe, and never reads source files again.
- Error `str` output is concise; detailed rendering is explicit. No raw host path
  is hidden or rewritten once supplied as a display origin.

## TDD matrix

- Sunny: accept version 1 independently in a nested graph and render a basic
  diagnostic at the exact coordinate.
- Rainy: distinguish every malformed/unsupported header and every error subclass
  while preserving causes and locations.
- Composite-complex: render a Unicode syntax failure three includes deep with
  CRLF excerpts, shadow-related locations, and byte-for-byte stable output.

## Completion evidence

Record RED, focused GREEN, snapshot/structural checks, full quality coverage,
and date in `progress.md`.
