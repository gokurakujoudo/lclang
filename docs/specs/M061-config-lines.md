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
- A definition continues only when the last non-space character outside a
  literal and before an optional comment is `\\`. Every non-final fragment
  requires its own marker; open delimiters never continue implicitly.
- Markers and trailing comments are masked with spaces and fragments are
  semantically joined by one space while original newlines and offsets remain
  available for diagnostics. Blank/comment-only continuation fragments,
  continuation on non-definition declarations, and semicolons are invalid.
- Lexical tracking understands literal prefixes, escaped quotes, f-strings,
  and comments without parsing the expression. Unfinished literals and stray
  closers are reported at their original positions.

## TDD matrix

- Sunny: scan mixed newline styles and explicitly continued bracketed definitions with
  exact original spans.
- Rainy: reject stray closers, unterminated literals, missing/redundant
  continuation markers, blank continuation fragments, and semicolons.
- Composite-complex: scan a CRLF document containing an f-string, nested display,
  embedded comment, blank line, and following declaration without span drift.

## Completion evidence

Record RED/GREEN commands, focused branch coverage, full quality output, and
the verification date in `progress.md`.
