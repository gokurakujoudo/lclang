# M086: CLI value and Frame construction

## Goal

Combine parsed CLI values with configuration and presets into an owned runtime
Frame using explicit precedence and namespaces.

## Module and test layout

- Binding lives in `pylcl/cli/binding.py`; invocation-owned runtime resources
  live in `pylcl/cli/runtime.py`.
- Tests live in `tests/cli/test_binding.py` and reuse config/runtime fixtures only
  through dedicated support modules.
- Production files remain under 200 lines and all callables/value classes,
  including private ones, use full English rST docstrings.

## Contract

- Parsed values are exposed as immutable namespace `cli`; invocation metadata is
  exposed as immutable namespace `context`. They never overwrite config names.
- The base Preset is applied to config definitions by the existing FrameFactory.
  Namespace lookup precedence is local LCL scope, config definitions, then preset;
  `cli` and `context` are explicit reserved preset names and conflicts fail early.
- Parameter defaults are ordinary parsed values. LCL expressions used as explicit
  computed defaults evaluate only after the Frame exists and may reference config
  and earlier declared parameters, never later parameters or handler results.
- `CliFrame` owns exactly one Frame and any invocation-created config loader. Its
  async close is shielded, idempotent, reverse-order, and does not close
  caller-owned streams, resolver, preset, or parent Frame.
- Failure during loading, default evaluation, or binding closes all acquired
  resources and preserves the primary error plus cleanup context.

## TDD matrix

- Sunny: bind parsed values/config/preset, evaluate computed defaults, and inspect
  the two namespaces and ownership.
- Rainy: reject namespace collisions, forward default references, load/evaluation
  failure, and verify cleanup without closing caller resources.
- Composite-complex: build concurrent invocations from one config/factory with
  different CLI values, async defaults, parent/preset data, and isolated cleanup.

## Completion evidence

Ledger RED/GREEN commands, lifecycle/dependency assertions, full quality coverage,
and verification date.
