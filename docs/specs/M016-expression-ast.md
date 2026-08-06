# M016: expression AST families

## Goal

Define immutable, evaluator-neutral node values required by the ordinary Pratt
grammar before parser control flow is introduced.

## Module and test layout

- `pylcl/ast/operators.py` and `tests/ast/test_operators.py` own stable unary,
  binary, Boolean, and comparison operator enums.
- `pylcl/ast/expressions.py` and `tests/ast/test_expressions.py` own unary,
  binary, Boolean, conditional, and null-coalescing nodes.
- `pylcl/ast/primaries.py` and `tests/ast/test_primaries.py` own attribute,
  safe-attribute, subscript, slice, and call nodes. `call_arguments.py` and its
  mirrored test module own the four explicit call-argument forms.
- `pylcl/ast/displays.py` and `tests/ast/test_displays.py` own list, set, dict,
  key/value, positional-unpack, and keyword-unpack values.

Each production module stays below 200 lines and has one mirrored unit-test
module. Package `__init__.py` only re-exports these values.

## Contract

- Operator enums have stable source-spelling values and no evaluator behaviour.
- Every node is a frozen, slotted dataclass inheriting `LclAstNode`.
- `children()` returns only AST children, exactly once, in deterministic source
  order; enum flags, names, and optional scalar metadata are excluded.
- Attribute names and keyword argument names are non-empty.
- Slices preserve optional lower, upper, and step expressions.
- Calls preserve positional/keyword order through explicit argument node values.
- Dict entries and unpacking use distinct nodes so parser, printer, evaluator,
  and dependency analysis never infer meaning from tuple shape.
- Constructors reject empty names and invalid comparison cardinality.
- Every production docstring satisfies the English rST contract from M007.

## TDD evidence

RED must fail because the four AST family modules are absent. GREEN requires
all mirrored tests. DONE requires the full quality gate and documentation sync.
