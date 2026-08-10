# M094: CLI literal host overrides

## Goal

Represent ordinary CLI override values as external-provided strings in the
override Frame while retaining successfully parsed `LCL[...]` values as lazy
LCL definitions.

## Module and test layout

- Override classification remains pure in `pylcl/cli/parser.py`; Frame assembly
  remains in `pylcl/cli/binding.py`.
- Behavioural coverage lives in `tests/cli/test_parser.py`,
  `tests/cli/test_binding.py`, and `tests/cli/test_module_entrance.py`.
- Runtime config text, when used, is a static case fixture and enabled logs stay
  beneath automatically cleaned temporary directories.

## Contract

- An override value is a lazy definition only when the entire token uses
  `LCL[...]`, its body is non-empty, and that body parses successfully. The
  parsed AST is stored in the `cli_overrides` module without evaluation.
- Every other override value—including ordinary text, empty markers, incomplete
  markers, and malformed expressions—is stored verbatim as a local host value in
  the `cli_overrides` Frame. It remains a Python `str` and is reported by
  `inspect_variable` as `ExternalProvided`.
- M097 adds one non-string override shape: omitting the value stores exact
  external-provided boolean `True`. All explicitly supplied values retain this
  milestone's string/lazy-marker contract.
- Definition and host-value override names are disjoint. Both have the same CLI
  precedence over config/default/preset layers, remain visible through the final
  `cli_runtime` Frame, and retain their exact raw strings in `CliParams.overrides`.
- `python -m pylcl.cli parse_lcl -o RESULT 100` prints exactly one external
  string node for `RESULT`. In `LCL[a+b]`, literal overrides `a` and `b` render
  as external string leaves, while `RESULT` remains a non-evaluated definition.
- `LCL['100']` is deliberately different from literal `100`: it remains a lazy
  constant definition until use. `eval_lcl` returns `100` for either spelling,
  preserving evaluation output while inspection exposes their different origins.

## TDD matrix

- Sunny: inspect plain `RESULT=100` as an external-provided `str`; evaluate it
  unchanged.
- Rainy: inspect empty/malformed LCL markers as exact external strings and prove
  no parser failure or evaluation occurs.
- Composite-complex: inspect lazy `RESULT=a+b` with two external literal leaves,
  then evaluate the same hierarchy as string concatenation while raw params keep
  every original token.

## Completion evidence

Record focused RED/GREEN commands, exact rendered nodes, full CLI and quality
results, and the verification date in `progress.md` before DONE.
