# M070: configuration public API and runtime bridge

## Goal

Expose a small async-first configuration API and convert merged definitions into
the existing Module, FrameFactory, and Preset runtime abstractions.

## Module and test layout

- Orchestration lives in `pylcl/config/api.py`; runtime conversion lives in
  `pylcl/config/runtime.py`; curated exports live in `pylcl/config/__init__.py`.
- Tests live in `tests/config/test_api.py` and `tests/config/test_runtime.py`.
- Production files remain under 200 lines, with complete English rST docstrings
  on every public/private callable and value class.

## Contract

- `parse_config(text, *, source_name)` synchronously parses one in-memory source
  without resolving includes. `load_config(source, *, resolver)` asynchronously
  resolves, parses, and merges a graph and returns immutable `Config`.
- `Config` exposes version, root origin, definitions, provenance history, and
  conversion to an immutable runtime `Module`. It never evaluates on inspection.
- `Config.frame_factory(*, preset=None, parent=None, limits=None)` delegates to
  the established runtime factory. The caller owns every created Frame and must
  close it; configs and factories are reusable immutable snapshots.
- `evaluate_config(...)` is async convenience for one owned Frame and guarantees
  cleanup. No new synchronous evaluation boundary is added; existing
  `evaluate_sync` remains the only sync convenience for evaluation.
- Root `pylcl` exports do not grow. Advanced names are curated under
  `pylcl.config`, with typed signatures and stable `__all__`.

## TDD matrix

- Sunny: parse/load, inspect provenance, build independent Frames, and evaluate a
  config using a standard Preset.
- Rainy: reject unresolved memory includes, resolver failures, invalid runtime
  arguments, and prove convenience cleanup after evaluation failure.
- Composite-complex: load a shadowing include graph, combine a parent and preset,
  evaluate concurrent names, inspect dependencies, and close all resources.

## Completion evidence

Record API RED, focused GREEN, strict type/doc/export checks, full quality
coverage, and verification date in `progress.md`.
