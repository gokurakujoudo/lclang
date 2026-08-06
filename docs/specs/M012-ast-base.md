# M012: immutable AST base and visitor

## Contract

All LCL syntax nodes derive from frozen, slotted `LclAstNode`; contain a source
span; compare structurally; expose children in source order; and support
pre-order traversal. AST objects contain no evaluator state and are safe to
cache or share between tasks.

`LclVisitor[ResultT]` defines one generic `visit(node)` entry. Nodes delegate
through `accept`, allowing evaluators, printers, and analyses to own dispatch.
The initial concrete nodes are constants, variable names, and tuple displays.

Programmatic nodes default to `UNKNOWN_SPAN`. Parsed nodes later receive exact
spans. Variable-name nodes reject empty identifiers.

## Test cases

- Frozen nodes reject mutation and compare structurally.
- Tuple children and pre-order traversal preserve source order.
- `accept` returns the visitor result.
- Empty variable names are rejected.

## Acceptance

AST tests and the complete quality script pass with at least 99% branch
coverage and without importing Python's `ast` module in runtime AST code.
