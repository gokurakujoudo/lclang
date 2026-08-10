# M086: layered CLI Frame construction

## Goal

Build and own the exact invocation Frame hierarchy from command preset/defaults,
optional static configuration, raw CLI overrides, and runtime values.

## Module and test layout

- Binding and invocation-owned Frame-stack lifecycle live in
  `pylcl/cli/binding.py`.
- Tests mirror both modules under `tests/cli/` and use dedicated static config
  support fixtures.
- Production files remain under 200 lines and all callables/value classes,
  including private ones, use full English rST docstrings.

## Contract

- Construct invocation-owned Frames in this parent-to-child order:
  `LCL_IMPORTS(preset) -> command/log defaults -> config -> CLI overrides ->
  cli-runtime`. Canonical runtime/builtin/root ancestors are borrowed.
- Parameter defaults other than `None` and `LogConfig` defaults are constant AST
  definitions. Command preset values are copied into the imports Frame.
- With `-c`, load the exact `.lclcfg` path through the existing async filesystem
  API and retain its lazy winning definitions. Without it, use an empty config
  module. Unit tests use static source fixtures declared with each test case.
- Literal and malformed-marker overrides become local host-provided strings.
  Successfully parsed `LCL[...]` bodies become lazy AST definitions. Repeated
  keys have already been reduced by the parser.
- The override Frame exposes immutable host values `as_of_date`, `dryrun`, and
  `cli_params`; these names cannot be user overrides. The empty child runtime
  Frame is the `CliContext.frame` reference.
- Validate required parameters with non-evaluating `Frame.has` after construction.
  Do not fetch/type-check parameter values; `value_type` is help metadata only.
- The owned stack closes every created Frame in reverse order, shielded and
  idempotent, without closing canonical ancestors. Binding/load/validation failure
  closes acquired Frames and retains primary plus cleanup diagnostics.

## TDD matrix

- Sunny: verify every precedence boundary, literal/deferred override shape,
  runtime values, required presence, lazy access, and reverse close.
- Rainy: cover missing required names, invalid/missing config, expression failure
  on use, reserved collisions, partial construction, and cleanup failure.
- Composite-complex: build concurrent invocations from one static included-config
  fixture with different preset/default/config/override/runtime values and prove
  lazy caches, dependencies, Frames, and cleanup remain isolated.

## Completion evidence

Ledger RED/GREEN commands, lifecycle/dependency assertions, full quality coverage,
and verification date.
