# M017: Pratt parser core

## Goal

Parse literal and name atoms, grouping parentheses, unary operations, and the
complete arithmetic/bitwise binary precedence ladder into custom AST nodes.

## Module and test layout

- `pylcl/lang/parser/stream.py` and `tests/lang/parser/test_stream.py` own token
  lookahead, matching, required-token diagnostics, and newline normalization.
- `pylcl/lang/parser/atoms.py` and `tests/lang/parser/test_atoms.py` own literal,
  name, constant-keyword, grouping, and adjacent-literal parsing.
- `pylcl/lang/parser/pratt.py` and `tests/lang/parser/test_pratt.py` own binding
  powers, unary parsing, binary reduction, complete-input validation, and the
  initial public `parse_expression` entry point.

## Contract

- Names, decoded numeric/text/bytes literals, and `True`, `False`, and `None`
  become the corresponding immutable atom nodes with exact source spans.
- Adjacent text literals concatenate; adjacent bytes concatenate; mixed text
  and bytes are rejected. F-string semantic conversion is deferred to M025.
- Parentheses group one expression. Empty and comma-containing parentheses are
  reserved for the display milestone.
- Unary `+`, `-`, `~`, and `not` use Python-compatible binding.
- The binary ladder, from tight to loose, is `**`, multiplicative, additive,
  shifts, `&`, `^`, and `|`. Power is right-associative and binds less tightly
  than a unary operator on its right but more tightly than a unary operator on
  its left.
- A public parse consumes exactly one complete expression, ignores physical
  newline tokens only as separators, and raises source-aware `LclSyntaxError`
  for empty input, missing delimiters, reserved forms, or trailing tokens.
- The optional origin and language version are explicit; only LCL V1 is
  accepted. No Python AST, `eval`, `exec`, or bytecode is used.
- Every public docstring satisfies M007's English rST contract.

## TDD evidence

RED must fail because the parser package is absent. GREEN requires all three
mirrored parser tests. DONE requires the full quality gate and README sync.
