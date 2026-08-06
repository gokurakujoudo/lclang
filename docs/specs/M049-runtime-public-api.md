# M049: stable 0.1 runtime and standard-preset public API

## Goal

Expose a small stable package-root workflow for constructing and evaluating
runtime modules with the reviewed standard preset, while preserving clear
advanced runtime and stdlib namespaces.

## Public surface

The package root adds exactly these 0.1 runtime names:

- `Module`, `Frame`, `FrameFactory`, `Preset`, and `EvaluationLimits`;
- `DependencySnapshot` as the return value for Frame dependency inspection;
- `STANDARD_PRESET` as the reviewed built-in namespace preset.

Existing language, source, identifier, error, and version exports remain stable.
Dependency graph construction/tracing/reconciliation utilities remain under
`pylcl.runtime`. Manifest types and individual helpers remain under
`pylcl.stdlib`; `STANDARD_MANIFESTS` also remains there for advanced inspection.

## Contract

- Every added root symbol is identical to its canonical subpackage export and
  appears once in root `__all__`.
- Importing `pylcl` assembles only immutable in-memory standard metadata; it
  performs no evaluation, task creation, I/O, environment access, or discovery.
- A root-only workflow can parse an expression, construct a Module, create a
  Frame through FrameFactory plus STANDARD_PRESET, evaluate a value, inspect its
  DependencySnapshot, and close the Frame.
- Direct root `Frame` construction remains equivalent and available.
- Advanced dependency functions, concrete helpers, and manifest construction
  types are intentionally absent from the root to avoid an unstable flat API.
- The distribution version remains unchanged until the M050-M051 0.1 release
  documentation and candidate gates complete.
- Root integration introduces no new implementation modules or runtime
  dependency. Tests live in `tests/test_runtime_public_api.py` as an acceptance
  mirror of `pylcl/__init__.py`.

## TDD evidence

RED requires the seven primary root attributes to be absent. GREEN requires
identity/`__all__` checks, namespace-boundary checks, and the complete root-only
async workflow. DONE requires the complete quality gate and synchronized
bilingual README/progress documentation.
