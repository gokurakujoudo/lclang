# M062: configuration whitespace and comments

## Goal

Specify which logical lines are ignorable and remove comments without damaging
literal content or diagnostic coordinates.

## Module and test layout

- Classification and comment stripping live in `pylcl/config/comments.py`.
- Tests mirror that boundary in `tests/config/test_comments.py`.
- Every private/public production callable and value class has a full English
  rST docstring; source modules remain under 200 lines.

## Contract

- Horizontal space surrounding declarations is insignificant. A line containing
  only whitespace or a comment is classified as ignorable.
- `#` begins a comment only outside string/bytes literals and outside the literal
  text of an f-string. A `#` in an f-string replacement expression follows the
  LCL lexer rules.
- Stripping replaces comment characters with spaces rather than shortening the
  source, preserving all offsets and columns for later parser errors.
- Comments may follow a complete declaration or appear on physical continuation
  lines. They cannot provide an implicit continuation after a closed expression.
- Encoding cookies, shebangs, block comments, and nested comment syntax have no
  special meaning; they are ordinary line comments or invalid declaration text.

## TDD matrix

- Sunny: ignore blank/full-comment lines and strip trailing comments while
  retaining exact columns.
- Rainy: prove that a comment cannot hide an illegal second declaration and that
  unterminated strings are still diagnosed.
- Composite-complex: classify multiline displays and f-strings containing literal
  `#` characters, replacement expressions, trailing comments, and CRLF input.

## Completion evidence

The ledger records the failing test, focused GREEN suite, full quality gate,
coverage, and verification date before this milestone becomes DONE.
