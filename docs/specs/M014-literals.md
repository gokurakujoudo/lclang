# M014: numeric and string literals

## Goal

Decode the non-interpolated literal vocabulary without relying on Python's AST,
`eval`, `exec`, bytecode, or third-party packages. Adjacent string or bytes
tokens remain separate lexical values for deterministic parser-side joining.
F-strings are reserved for M015.

## Module boundary

- `pylcl/lang/lexer/literals.py` owns literal prefix recognition, numeric
  conversion, quoted boundaries, and the immutable literal match value.
- `pylcl/lang/lexer/escapes.py` owns raw, text, bytes, and escape decoding.
- `pylcl/lang/lexer/scanner.py` delegates literal slices to that module.
- `tests/lang/lexer/test_literals.py` and `test_escapes.py` mirror those modules;
  scanner tests cover only delegation and source-range integration.

## Contract

- Decimal, binary, octal, and hexadecimal integers support valid underscore
  separators and produce Python `int` values.
- Decimal floating-point syntax supports fraction and exponent forms and
  produces `float` values. Complex literals are outside LCL V1.
- Single-, double-, and triple-quoted text produces `str`; `b`, `r`, `br`, and
  `rb` prefixes produce bytes or raw values as appropriate, case-insensitively.
- Text escapes support the standard single-character escapes, octal, `\xhh`,
  `\uhhhh`, `\Uhhhhhhhh`, and named Unicode escapes. Bytes reject Unicode and
  non-ASCII source characters.
- Raw literals preserve backslashes but still require a closing quote.
- Newlines are legal only inside triple-quoted literals.
- Invalid digits, separators, escapes, prefixes, encoding, or termination raise
  a source-aware `LclSyntaxError` covering the attempted literal.
- Adjacent literals produce adjacent tokens; concatenation and mixed-kind
  rejection are parser responsibilities.

## TDD evidence

RED must demonstrate missing literal decoding. GREEN runs the mirrored literal
and scanner tests. DONE requires the complete quality gate and documentation
synchronization.
