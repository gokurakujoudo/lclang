# M013: core lexer

## Goal

Introduce source-aware tokens and deterministic scanning for identifiers,
keywords, punctuation, operators, whitespace, comments, and physical newlines.
Literal payload decoding belongs to M014 and f-string structure belongs to M015.

## Module boundary

- `pylcl/lang/lexer/tokens.py` owns immutable token kinds and token values.
- `pylcl/lang/lexer/scanner.py` owns cursor movement and core tokenization.
- `pylcl/lang/lexer/__init__.py` contains re-exports only.
- Tests mirror those modules under `tests/lang/lexer/`.

Neither token values nor the scanner import parser, evaluator, runtime, config,
or CLI modules.

## Contract

- `TokenKind` distinguishes identifiers, reserved keywords, punctuation,
  operators, newlines, and end-of-input.
- Every `Token` preserves its exact lexeme and a half-open `SourceSpan`.
- Identifiers use Python's Unicode identifier predicate. The core scanner
  recognizes ASCII operator and punctuation syntax.
- Spaces, tabs, form feeds, carriage returns, and `#` comments are ignored.
  A bare or CRLF line ending produces exactly one `NEWLINE` token.
- The scanner emits longest operators first, so `**`, `//`, `<<`, `>>`, `<=`,
  `>=`, `==`, `!=`, `?.`, and `??` cannot split into shorter tokens.
- Keyword recognition is explicit and stable for LCL V1.
- The stream always ends with exactly one zero-width `EOF` token.
- An unsupported character raises `LclSyntaxError` with its source span.
- Cursor offsets and columns count Unicode code points, not encoded bytes.

## TDD evidence

The RED phase must fail because `pylcl.lang.lexer` is absent. GREEN requires
the mirrored lexer tests. DONE requires the complete quality gate with at least
99% branch coverage and synchronized progress and README files.
