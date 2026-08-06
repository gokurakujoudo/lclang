# M018: parser primaries

## Goal

Extend parsed atoms with arbitrarily chained attribute, null-safe attribute,
subscription, slicing, and call operations without complicating Pratt binding.

## Module and test layout

- `pylcl/lang/parser/primaries.py` owns the postfix loop and focused helpers.
- `tests/lang/parser/test_primaries.py` mirrors that module.
- `stream.py` gains bounded lookahead with coverage in its existing mirror.
- `pratt.py` delegates only after parsing an atom, preserving one-way ownership.

## Contract

- `value.name` and `value?.name` require one identifier and may chain.
- `value[index]` parses one complete index expression.
- Slices preserve independently optional lower, upper, and step expressions;
  more than two colons are rejected. Extended comma slicing belongs to M019.
- Calls preserve source order through explicit positional, starred, keyword, and
  keyword-unpack argument wrapper nodes. Empty calls and trailing commas work.
- Explicit keyword names are unique. Positional arguments cannot follow an
  explicit keyword or keyword unpack; starred positional arguments cannot
  follow keyword unpack.
- Postfix operations bind tighter than power and every other operator.
- Missing names, expressions, delimiters, invalid keyword targets, duplicates,
  and invalid ordering raise source-aware `LclSyntaxError`.
- All nodes span their full primary source; public docstrings satisfy M007.

## TDD evidence

RED must fail because the parser-primary module is absent and Pratt returns only
atoms. GREEN requires the mirrored primary and stream tests. DONE requires the
full quality gate and documentation synchronization.
