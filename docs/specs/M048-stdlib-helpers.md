# M048: reviewed zero-dependency standard-library helpers

## Goal

Ship a deliberately small standard preset of deterministic data helpers that
cooperate with async evaluation while exposing no ambient I/O or code-loading
capabilities.

## Module and test layout

- `pylcl/stdlib/iterables.py` owns async sync/async-iterable collection helpers.
- `pylcl/stdlib/text.py` owns async joining and deterministic line splitting.
- `pylcl/stdlib/data.py` owns shallow immutable mapping merge and lookup.
- `pylcl/stdlib/json_values.py` owns strict JSON encoding and decoding.
- `pylcl/stdlib/builtins.py` owns reviewed manifests and `STANDARD_PRESET`.
- Matching test modules under `tests/stdlib/` mirror every production module.

## Contract

- `collect(values)` asynchronously consumes a synchronous or asynchronous
  iterable into a new list in iteration order.
- `first(values, default=None)` returns the first sync/async item and stops
  consuming immediately, or returns `default` for an empty iterable.
- `join(separator, values)` asynchronously consumes sync/async string values
  and joins them. A non-string separator or item raises `TypeError`.
- `lines(value, keep_ends=False)` returns `str.splitlines` output and requires a
  string value plus an actual boolean flag.
- `merge(*mappings)` performs a shallow left-to-right update and returns a
  read-only insertion-ordered mapping. Every input must implement Mapping.
- `lookup(mapping, key, default=None)` returns the mapped value or default and
  requires a Mapping without suppressing mapping protocol failures.
- `json_encode(value)` uses UTF-8-friendly compact standard JSON, preserves
  mapping order, and rejects NaN/infinity and unsupported values.
- `json_decode(value)` requires text and uses the standard strict JSON decoder.
  Decoder and encoder exceptions propagate for the evaluator to structure.
- `STANDARD_MANIFESTS` contains namespaces in stable order `iter`, `text`,
  `data`, `json`; entry order is stable and every entry has review metadata.
  `STANDARD_PRESET` is assembled once from exactly those manifests.
- Helpers perform no filesystem, environment, network, subprocess, thread,
  reflection, dynamic import, or arbitrary source execution. Only Python's
  standard library and existing pylcl iteration/manifest primitives are used.
- Public functions use complete English rST documentation, including arguments,
  results, intentional failures, and special behaviour. Production and mirrored
  test modules remain below 200 physical lines.

## TDD evidence

RED requires concrete helper and standard preset imports to fail. GREEN requires
sync/async iteration, early termination, type errors, immutable merge precedence,
lookup outcomes, strict JSON success/failure, stable reviewed manifests, and an
end-to-end Frame expression using `STANDARD_PRESET`. DONE requires the complete
quality gate and synchronized bilingual README/progress documentation.
