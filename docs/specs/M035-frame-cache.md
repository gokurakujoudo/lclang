# M035: runtime modules and local Frame caching

## Goal

Introduce immutable runtime module snapshots and a resolver-compatible Frame
that lazily evaluates local definitions and caches both successful values and
ordinary failures.

## Module and test layout

- `pylcl/runtime/modules.py` owns the named immutable definition snapshot.
- `pylcl/runtime/frames.py` owns local lookup, lazy evaluation, and cache state.
- `tests/runtime/test_modules.py` mirrors module validation and snapshotting.
- `tests/runtime/test_frames.py` mirrors lazy lookup and result/failure caching.

## Contract

- `Module(name, definitions)` requires non-empty module and variable names,
  copies its input mapping, and exposes a read-only definition snapshot.
- A definition is one semantic `LclAstNode`; duplicate names are resolved by the
  caller's mapping construction before the Module boundary.
- `Frame(module, frame_id, values=...)` requires a non-empty identifier,
  snapshots optional host bindings, and implements the evaluator `Resolver`
  protocol. Local definitions shadow host bindings.
- `Frame.get(name)` and resolver lookup lazily evaluate a definition with the
  same Frame as resolver, enabling local definition references.
- A successful result is cached by variable name and returned by identity on
  subsequent requests. An ordinary `Exception` is likewise cached and the same
  exception instance is re-raised.
- Direct `BaseException` subclasses such as cancellation are never cached.
- Unknown variables raise `LclNameError`; resolver lookup retains the requesting
  name-node span while `get` has no source span.
- M035 does not promise concurrent single-flight, parent lookup, recalculation,
  resource limits, or close behaviour; those are isolated in M036-M041.
- Public values and methods use complete English rST documentation; every
  implementation file remains below 200 lines.

## TDD evidence

RED requires imports of the absent runtime package to fail. GREEN requires
module snapshot/validation plus lazy value and failure-cache cases. DONE
requires the complete quality gate and synchronized README/progress documents.
