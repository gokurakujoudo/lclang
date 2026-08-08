# M024: canonical source printer

## Goal

Render every implemented semantic AST node as deterministic LCL V1 source that
reparses to the same structure and preserves operator meaning.

## Module and test layout

- `pylcl/lang/printer/atoms.py`, `expressions.py`, `primaries.py`,
  `collections.py`, and `forms.py` own their matching AST families.
- Each module has the same-named mirror under `tests/lang/printer/`.
- `pylcl/lang/printer/dispatch.py` owns dispatch, parenthesization, and the public
  `to_source` entry point; `test_dispatch.py` mirrors integration and errors.
- Package `__init__.py` re-exports only public entry points.

## Contract

- Output is ASCII punctuation plus Unicode identifiers/text as required; spaces
  and delimiters follow one stable canonical style.
- Parentheses are inserted only when required by precedence, associativity, or
  form placement. Printing never changes power/unary, Boolean, comparison,
  coalescing, or conditional meaning.
- String and bytes constants use a deterministic escaped representation.
- Every display, unpacking form, comprehension, call argument, slice, f-string
  semantic node, and function/control form has a canonical spelling.
- Parsing canonical source and printing it again is idempotent. For parser-
  supported nodes, parse-print-parse preserves node types, operators, scalar
  metadata, and child structure while source spans may differ.
- Unknown custom `LclAstNode` subclasses raise `TypeError` rather than falling
  back to `repr`.
- Printing is pure, synchronous, and has no runtime or evaluation dependency.
- Public docstrings satisfy M007 and every source module stays below 200 lines.

## TDD evidence

RED must fail because the printer package is absent. GREEN requires each
mirrored renderer suite plus integration round trips. DONE requires the complete
quality gate and documentation synchronization.
