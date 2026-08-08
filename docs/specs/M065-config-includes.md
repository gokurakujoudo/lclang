# M065: configuration using declarations and resolver protocol

## Goal

Add explicit using declarations and an async, host-controlled source resolver
without coupling the configuration language to a filesystem.

## Module and test layout

- Include parsing lives with declarations; resolution lives in
  `pylcl/config/includes.py` and its protocol in `pylcl/config/protocols.py`.
- Tests live in `tests/config/test_includes.py`; fake resolvers live in
  `tests/config/support.py`.
- Production modules remain below 200 lines. Every callable and value class,
  including private ones, has a complete English rST docstring.

## Contract

- Using syntax is `using "target"`; the target is exactly one non-empty normal
  or raw LCL string literal decoding to `str`. F-strings, bytes, adjacent
  literals, continuation, computed targets, and trailing tokens are invalid.
- Root and using targets end exactly in `.lclcfg`. Absolute paths remain
  absolute; relative paths resolve from the importer directory. A decoded
  leading `__dir__` path token expands to that directory and may be followed by
  any number of `..` components.
- `ConfigSourceResolver.resolve(path, *, importer)` is async and returns
  immutable `ResolvedConfigSource(identity, display_name, path, text)`.
- Resolver identities are non-empty stable strings used for deduplication and
  cycles. Display names are diagnostic only; source text must be Unicode.
- Resolution walks declarations in source order and recursively parses each
  returned document. A using declaration performs no expression evaluation.
- Resolver exceptions are wrapped as `LclConfigUsingError` with target,
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
