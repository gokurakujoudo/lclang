# M098: canonical AST value inspection representation

## Goal

Render supported `LclAstNode` objects and evaluated LCL function closures stored
as dependency-tree values with their concrete value type and canonical LCL
expression instead of their Python dataclass representation.

## Module and test layout

- Value payload formatting remains centralized in
  `pylcl/runtime/frame/inspection.py` and reuses the existing canonical
  `pylcl.lang.printer.to_source` boundary.
- Behavioral coverage remains in
  `tests/runtime/frame/test_inspection.py` for external, cached, and
  native-provenance values.

## Contract

- When `VariableInspectionTree.current_value` is a supported `LclAstNode`, its
  payload is exactly `<concrete-node-type>: <canonical-LCL-expression>`.
  Example: `LclBinary: base + 2`.
- An evaluated `LclFunctionValue` retains the `LclFunction` node that created
  it. Its ordinary `repr` is the canonical source of that node, so the existing
  typed inspection payload becomes exactly
  `LclFunctionValue: <canonical-function-expression>` without exposing bound
  parameter, resolver, evaluator, closure, or source-span implementation state.
- The same conversion applies wherever an ordinary typed value payload is used:
  external host bindings, successful cached definition results, and the typed
  fallback for a native-provenance non-callable value.
- Conversion uses the public canonical printer, preserving precedence,
  delimiters, literal escaping, function syntax, comprehensions, and all other
  implemented source-rendering rules. Physical CR/LF characters remain escaped
  so each inspection node occupies one line.
- Definition syntax before `(Status)` is unchanged. A cached definition that
  returns an AST value therefore shows both its own definition and the typed
  canonical value, for example
  `result@frame: supplied (Cached) LclBinary: base + 2`.
- Ordinary Python values, exceptions, missing values, native functions,
  namespaces, statuses, paths, dependencies, and side-effect-free inspection
  behavior remain unchanged.
- Unsupported custom subclasses that the canonical printer rejects retain the
  ordinary compact Python repr rather than making inspection fail.

## TDD matrix

- Sunny: inspect a supported external binary AST and assert exact type plus
  canonical expression with no dataclass field dump.
- Rainy: retain normal strings and an unsupported custom AST subclass without
  raising or changing its ordinary compact repr.
- Composite-complex: cache a definition returning a function/comprehension AST
  host value and inspect the same supported AST through native fallback; assert
  exact source, one-line rendering, object identity, and zero extra evaluation.
- Screenshot regression: evaluate a fixed-point-produced quicksort closure,
  cache it in a Frame, and assert its tree line contains the canonical inner
  function expression without `BoundParameter`, resolver, evaluator, or
  `SourceSpan` dataclass output.

## Completion evidence

Record focused RED/GREEN commands, exact external/cached/native lines, full
quality results, and the verification date in `progress.md` before marking this
milestone DONE.
