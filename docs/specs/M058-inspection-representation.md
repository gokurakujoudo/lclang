# M058 - Inspection tree representation

Status: VERIFIED

## Goal

Replace the dataclass-like `VariableInspectionTree` representation with a terse,
source-oriented line that users can read directly in logs and markdown trees.

## Contract

- `repr(tree)` has the exact shape
  `<var_name>@<definition_path>: [<definition> ](<status>) <typed-payload>`.
- `<var_name>` is `str(tree.var_name)`.
- `<definition_path>` joins `FrameId` values from lookup origin to selected owner
  with `/`, for example `request/rates`. It does not use Python list syntax.
- `<definition>` is the canonical LCL source produced by the existing
  precedence-aware `to_source()` printer. Exactly one space separates an AST
  from `(<status>)`. An external host-value node has no definition text and
  begins directly with `(<status>)`; an unresolved node retains `<missing>`.
- `<status>` is the public status value exactly: `Cached`, `NotEvaluated`, or
  `ExternalProvided`.
- `<typed-payload>` uses `current_exception` when present and otherwise
  `current_value`. An error is `<error type>: <error message>`, using the concrete
  class name and `str(error)` with one space after the colon. A value is
  `<type>: <single-line repr>`, including `NoneType: None` for unevaluated
  definitions. Physical CR/LF characters are escaped in both forms.
- The representation has no recursive children, AST/Frame repr, dependency
  count, surrounding class name, or trailing whitespace.
- `to_lines()` retains its indentation and prefix contract but uses the new
  representation for every node.

## Examples

```text
answer@frame-app: base + 2 (NotEvaluated) NoneType: None
base@frame-app: 40 (Cached) int: 40
rate@request/imports: (ExternalProvided) float: 0.2
missing@request/imports: <missing> (NotEvaluated) LclNameError: [LCL2001] unknown variable: missing
```

## Acceptance

- Sunny coverage proves exact definition source/spacing, joined lookup path,
  status, typed value, and markdown rendering for uncached/cached definitions.
- Rainy coverage proves omitted external definitions, the missing placeholder,
  error priority, and one-line escaping for unusual value/error text.
- Composite coverage proves a child-to-parent definition path and nested
  dependency lines use the same grammar without recursive repr expansion.
- Tutorials, runtime API reference, READMEs, changelog, and progress evidence
  describe the new output.
- Focused/full pytest, branch coverage, strict mypy, Ruff, documentation checks,
  isolated source policy, and `git diff --check` pass before VERIFIED.
