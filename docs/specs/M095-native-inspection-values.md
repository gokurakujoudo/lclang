# M095: native dependency-tree values

## Goal

Distinguish pylcl's canonical reviewed builtins and standard namespaces from
application-provided host values, and render every native value with the same
compact `type: repr` payload grammar without unstable addresses or namespace
implementation mappings.

M096 supersedes only the native payload spelling with the uniform
`Builtin Function: name` / `Builtin Namespace: name` grammar; provenance and
all other contracts below remain historical completion evidence.

## Module and test layout

- Canonical value provenance is owned by `Frame` construction and selected by
  the existing inspector in `pylcl/runtime/frame/`.
- Status and stable value formatting remain in
  `pylcl/runtime/frame/inspection.py`; concise namespace repr belongs to
  `pylcl/stdlib/namespaces.py`.
- Runtime behavior tests live in `tests/runtime/frame/test_inspection.py` and
  `tests/stdlib/test_namespaces.py`; the built-in CLI tree case lives in
  `tests/cli/test_module_entrance.py`.

## Contract

- `VariableInspectionStatus` adds public value `NativeProvided`. A selected host
  binding is `NativeProvided` only when its owning Frame was explicitly
  constructed with canonical native-value provenance. All ordinary Frame values,
  presets, CLI literals, and user-created lookalike Frame IDs remain
  `ExternalProvided`.
- The canonical `LCL_ROOT` values (`lhs` and reviewed standard namespaces) and
  canonical `LCL_BUILTINS` values are native. Empty `LCL_RUNTIME` and
  `LCL_IMPORTS` Frames do not confer provenance on descendant values.
- Native nodes have no AST definition or dependencies and expose the original
  uncalled/unawaited object as `current_value`. Inspection remains side-effect
  free and does not change evaluator lookup, precedence, caching, or cleanup.
- All value nodes retain the exact
  `name@path: (Status) <type>: <single-line repr>` form. External values continue
  using ordinary compact `repr`. Native Python types use their normal stable
  repr; native built-in functions use `<built-in function name>`; native Python
  functions use address-free `<function qualified_name>`.
- `StdlibNamespace.__repr__` is exactly
  `StdlibNamespace(namespace='<name>')`; it omits members, mapping proxies,
  function addresses, and recursive contents. A native namespace tree payload is
  therefore `StdlibNamespace: StdlibNamespace(namespace='<name>')`.
- Missing names remain `NotEvaluated`, definitions remain `NotEvaluated` or
  `Cached`, and user/CLI host bindings remain `ExternalProvided`. Status/rendering
  changes are additive public API behavior.

## TDD matrix

- Sunny: inspect `len`, a normal Python type/function, `lhs`, and `iter` through
  the canonical hierarchy and assert exact `NativeProvided` typed payloads.
- Rainy: create a user Frame named `LCL_BUILTINS` with the same callable and prove
  it remains external; retain missing, malformed, multiline, and closed behavior.
- Composite-complex: parse a CLI `RESULT` depending on `len`, `iter`, and external
  literal inputs; assert a non-evaluated root, native stable leaves, external
  application leaves, no memory addresses/mapping contents, and no evaluation.

## Completion evidence

Record focused RED/GREEN commands, exact native/external tree lines, full CLI and
quality results, and the verification date in `progress.md` before DONE.
