# M061: physical and logical configuration lines

## Goal

Convert configuration text into source-aware logical lines without interpreting
declarations or LCL expressions.

## Module and test layout

- Line normalization and scanning live in `pylcl/config/lines.py`.
- Tests live in `tests/config/test_lines.py`; shared origin factories remain in
  `tests/config/support.py`.
- Modules stay below 200 lines and all production callables and value classes
  use complete English rST docstrings.

## Contract

- Input is `str`. LF, CRLF, and CR are accepted and normalized for scanning
  while every emitted span still indexes the original source text.
- `LogicalLine` records text, start/end positions, physical line range, and its
  origin. Blank lines are emitted for M062 to classify rather than discarded.
- An unfinished LCL string or unmatched closing delimiter is reported as a
  configuration syntax error at the original position.
- A declaration continues only while `()`, `[]`, or `{}` nesting is open.
  Newlines inside quoted literals do not terminate a line. Backslash line
  continuation and semicolon-separated declarations are deliberately invalid.
- Delimiter tracking understands prefixes, escaped quotes, triple-quoted
  strings, f-string replacement fields, and comments without parsing the LCL
  expression itself.

## TDD matrix

- Sunny: scan mixed newline styles and multiline bracketed definitions with
  exact original spans.
- Rainy: reject stray closers, unterminated literals, backslash continuation,
  and semicolon-separated declarations with stable positions.
- Composite-complex: scan a CRLF document containing an f-string, nested display,
  embedded comment, blank line, and following declaration without span drift.

## Completion evidence

Record RED/GREEN commands, focused branch coverage, full quality output, and
the verification date in `progress.md`.
