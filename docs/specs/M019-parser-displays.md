# M019: parser displays

## Goal

Parse tuple, list, set, and dictionary displays with explicit iterable and
mapping unpack nodes while preserving grouping-parenthesis behaviour.

## Module and test layout

- `pylcl/lang/parser/displays.py` owns delimiter-specific display parsing.
- `tests/lang/parser/test_displays.py` mirrors the module.
- `atoms.py` delegates opening delimiters; `pratt.py` adds root-level tuple
  assembly; `primaries.py` adds comma-separated multi-index tuples.

## Contract

- `()` and comma-bearing parentheses produce tuple nodes; parentheses without a
  comma only group and extend the enclosed node's source span.
- Root-level comma expressions produce tuples, including a trailing comma.
- Lists allow ordinary and `*` unpack elements, including empty and trailing
  comma forms.
- `{}` is a dict. Non-empty braces choose set mode for ordinary/`*` elements or
  dict mode for key/value/`**` entries and reject mixed modes.
- Sets require at least one element. Dictionary entries remain explicit
  `LclKeyValue` or `LclDictUnpack` nodes in source order.
- Multi-index subscription such as `value[1, 2]` uses an `LclTuple` index.
  Comma-mixed extended slices are deferred to the comprehension milestone.
- Missing expressions/delimiters, invalid unpack placement, mode mixing, and
  stray colons raise source-aware `LclSyntaxError`.
- All display nodes span opening through closing delimiters; root tuples span
  first through last element. Public docstrings satisfy M007.

## TDD evidence

RED must fail because the display parser is absent and delimiters are rejected.
GREEN requires the mirrored display tests plus updated primary tests. DONE
requires the complete quality gate and documentation synchronization.
