# M015: f-string lexical and AST model

## Goal

Represent interpolated strings without asking the lexer to parse embedded LCL
expressions. The lexer preserves expression source and format structure; the
parser later converts expression fields into immutable AST nodes.

## Module boundary

- `pylcl/lang/lexer/fstring_values.py` owns immutable lexical parts, while
  `fstrings.py` owns brace-aware scanning within a recognized delimiter.
- `pylcl/ast/fstrings.py` owns semantic joined-string and formatted-value nodes.
- `literals.py` recognizes `f`, `fr`, and `rf` prefixes and delegates.
- Tests mirror the production modules at `tests/lang/lexer/test_fstrings.py`,
  `test_fstring_values.py`, and `tests/ast/test_fstrings.py`.

## Contract

- `f`, `F`, `fr`, and `rf` prefixes work with single, double, and triple quotes;
  bytes interpolation is rejected.
- Literal text uses the M014 escape decoder unless the raw prefix is present.
- `{{` and `}}` produce literal braces. An unmatched single brace is invalid.
- A replacement field preserves non-empty expression source, optional debug
  `=`, optional `!s`, `!r`, or `!a` conversion, and an optional format spec.
- Nested parentheses, brackets, braces, and quoted strings inside an expression
  do not terminate the field. Format specs may contain nested replacement
  fields and are represented recursively.
- Backslashes are forbidden in replacement expression source. Comments and
  empty replacement expressions are rejected for deterministic V1 behaviour.
- Lexical failures become source-aware `LclSyntaxError` values.
- `LclJoinedString` children are text constants and `LclFormattedValue` nodes;
  formatted nodes expose their expression followed by an optional format-spec
  node through deterministic `children()` traversal.

## TDD evidence

RED must fail because the lexical and AST f-string modules are absent. GREEN
runs both mirrored test modules. DONE requires the full project quality gate and
synchronized milestone documentation.
