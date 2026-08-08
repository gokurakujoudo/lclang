# M053: canonical Frame hierarchy and definition shortcuts

## Goal

Make the ordinary embedding path concise while giving every LCL run one explicit,
inspectable lookup hierarchy. Raw `Module`, `Frame`, `Preset`, and `FrameFactory`
construction remain compatible advanced APIs.

## Contract

- Lookup precedence is `LCL_ROOT -> LCL_BUILTINS -> LCL_RUNTIME -> LCL_IMPORTS
  -> user module`, where arrows point from parent to child and the nearest child
  wins.
- `LCL_ROOT` contains definition-scoped `lhs()` plus the reviewed LCL namespace
  mixin exposed by `STANDARD_PRESET`: `iter`, `text`, `data`, and `json`.
- `LCL_BUILTINS` contains a fixed, documented, ambient-I/O-free set of ordinary
  Python value types and functions. It excludes import, evaluation, compilation,
  reflection, process input, file access, and mutation helpers.
- `LCL_BUILTINS` additionally exposes locale-independent `parse_ymd` and
  `to_ymd` conversion between strict `YYYYMMDD` text and `datetime.date`.
- `LCL_RUNTIME` is the package's empty default run layer. Applications and the
  future CLI may instead supply one Frame per run, parented by `LCL_BUILTINS`,
  whose host bindings contain immutable CLI/context values.
- `LCL_IMPORTS` is the empty default import/preset layer parented by
  `LCL_RUNTIME`. A call-specific preset produces a fresh equivalent layer above
  the selected runtime base.
- Canonical ancestor Frames own no lazy definitions or event-loop tasks. Closing
  a user Frame does not close borrowed hierarchy ancestors.
- Frame name lookup has one recursive owner-selection rule: a local definition
  wins over a local host value, either local binding wins over every ancestor,
  and otherwise lookup continues through the parent chain.

## Public interfaces

- `pylcl.define_module(name: str, exprs: dict[str, str]) -> Module` parses every
  expression in insertion order and returns the existing immutable `Module`
  value. Input mappings and strings are never retained mutably.
- `pylcl.define_frame(module: Module | None = None, base: Frame = LCL_RUNTIME,
  preset: dict[str, object] | None = None) -> Frame` returns a fresh user Frame.
  `None` selects an empty user module; `None` preset reuses `LCL_IMPORTS` only
  with the default runtime and otherwise creates an empty imports layer.
- `LCL_ROOT`, `LCL_BUILTINS`, `LCL_RUNTIME`, and `LCL_IMPORTS` are package-root
  exports and stable Frame identities. The existing `STANDARD_PRESET` remains
  public for lower-level factory composition.
- `frame.has(name: str) -> bool` reports whether the shared lookup rule selects a
  definition or host value without evaluating it. `frame.get_definition(name:
  str) -> LclAstNode | None` returns the selected owner AST only when that
  binding is a definition; a missing name or a nearer host-value shadow returns
  `None`.
- `frame.derive(module: Module, values: dict[str, object] = {}) -> Frame` creates
  a fresh child whose borrowed parent is `frame`, immutable definitions are
  *module*, detached local host bindings are *values*, and Frame ID is the module
  name. The default dictionary is never mutated or retained.
- `frame.mixin(values: dict[str, object]) -> None` atomically copies a
  right-biased set of host bindings into an open Frame. New direct lookups and
  uncached evaluations observe the update; cached definition results/failures
  remain snapshots until explicitly recalculated. Local module definitions
  continue to shadow mixed values with the same name.
- The preferred documented workflow uses `define_module` and `define_frame`.
  Existing constructors remain documented as the advanced explicit boundary.

## Failure behaviour

- Non-string module names, non-dictionary expression collections, non-string
  definition names or sources, non-Module module values, non-Frame bases, and
  non-dictionary presets raise `TypeError` before a Frame is returned.
- `derive` rejects a non-Module module or non-dictionary values with `TypeError`;
  empty value names retain Frame's `ValueError` contract.
- `mixin` rejects non-dictionaries with `TypeError`, validates every key before
  committing so invalid empty keys cause `ValueError` without a partial update,
  and rejects closing/closed Frames with `LclClosedFrameError`.
- Empty module/definition/preset names retain the existing `ValueError`
  contracts. Invalid expressions retain structured `LclSyntaxError` details.
- Empty lookup names raise `ValueError` consistently across `get`, `has`, and
  `get_definition`. Inspection changes no cache, task, dependency, or lifecycle
  state.
- Construction failure publishes no partially usable Module or Frame and never
  mutates a caller mapping.

## Test cases

- Sunny: define a module entirely from source strings and evaluate standard LCL
  namespaces plus built-in `len`/`range` through the default hierarchy.
- Rainy: reject malformed expressions and every invalid shortcut input category,
  while proving input mappings remain detached.
- Composite-complex: create a per-run CLI Frame above `LCL_BUILTINS`, add a
  call-specific preset, and prove user, preset, runtime, builtin, and root lookup
  plus shadowing in the exact parent chain.
- Lookup inspection: prove local and ancestor definitions, host values, missing
  names, definition-over-value precedence, value-over-ancestor-definition
  masking, empty-name validation, and zero evaluation side effects.
- Derivation: prove parent identity, module-derived ID, detached/default values,
  nested lookup/shadowing, independent cache/lifecycle, validation, and that
  closing a child does not close its borrowed parent.
- Value mixin: prove detached right-biased updates, module precedence,
  child-visible parent updates, cached-snapshot preservation plus explicit
  recalculation, atomic validation failure, closed rejection, and ``None``
  return.

## Acceptance

Record the focused RED and GREEN commands, full test count, branch coverage,
strict mypy, Ruff, source/docstring/line policy, diff check, synchronized English
and Chinese documentation, and verification date in `progress.md` before `DONE`.
