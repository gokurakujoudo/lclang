# M065: configuration includes and resolver protocol

## Goal

Add explicit include declarations and an async, host-controlled source resolver
without coupling the configuration language to a filesystem.

## Module and test layout

- Include parsing lives with declarations; resolution lives in
  `pylcl/config/includes.py` and its protocol in `pylcl/config/protocols.py`.
- Tests live in `tests/config/test_includes.py`; fake resolvers live in
  `tests/config/support.py`.
- Production modules remain below 200 lines. Every callable and value class,
  including private ones, has a complete English rST docstring.

## Contract

- Include syntax is `include "target"`; the target is exactly one non-empty LCL
  string literal and must decode to `str`. F-strings, bytes, trailing tokens, and
  computed targets are invalid.
- `ConfigSourceResolver.resolve(target, *, importer)` is async and returns
  immutable `ResolvedConfigSource(identity, display_name, text)`. The host owns
  target interpretation, decoding, authorization, and retrieval.
- Resolver identities are non-empty stable strings used for deduplication and
  cycles. Display names are diagnostic only; source text must be Unicode.
- Resolution walks declarations in source order and recursively parses each
  returned document. An include performs no expression evaluation.
- Resolver exceptions are wrapped as `LclConfigIncludeError` with target,
  importing span, and preserved cause; cancellation propagates unchanged.

## TDD matrix

- Sunny: resolve one and nested includes through an async in-memory resolver in
  declaration order.
- Rainy: reject malformed targets and wrap missing/invalid resolver results while
  preserving cancellation.
- Composite-complex: resolve a diamond graph with Unicode identities, delayed
  async sources, definitions around includes, and deterministic traversal events.

## Completion evidence

Record RED/GREEN commands, focused coverage, the full quality gate, and date in
`progress.md`.
