# M025: complete parser diagnostics and public API

## Goal

Close the V1 language-front-end slice by converting lexical f-string values to
semantic AST nodes, freezing parser failure behaviour, and publishing the
versioned parse and canonical-print entry points.

## Module and test layout

- `pylcl/lang/parser/fstrings.py` recursively converts lexical f-string parts;
  `tests/lang/parser/test_fstrings.py` mirrors its semantic and error cases.
- `pylcl/lang/parser/pratt.py` remains the version-validation and complete-input
  boundary; its existing mirror owns public parser diagnostic regressions.
- `pylcl/lang/__init__.py` and `pylcl/__init__.py` expose the stable front-end
  surface. `tests/test_public_api.py` verifies only those public exports.

## Contract

- Every `FStringValue` becomes an `LclJoinedString`. Text becomes
  `LclStringText`; fields become `LclFormattedValue` with a recursively parsed
  expression, conversion, debug flag, and recursively converted format spec.
- Invalid embedded expressions raise `LclSyntaxError` with code `LCL1001`, the
  outer f-string token span, and the original parser error as their cause.
- Empty input, malformed input, and unexpected trailing input remain
  `LclSyntaxError` values with a non-empty message, stable code, and source span.
- `parse_expression` accepts only `LanguageVersion.V1` and defaults to `LCL_V1`;
  unsupported values raise `ValueError` before parsing.
- `parse_expression` and `to_source` are importable from both `pylcl.lang` and
  `pylcl`. AST families remain namespaced under `pylcl.ast` rather than being
  duplicated at the package root.
- Public docstrings use English rST with parameters, return values, intentional
  errors, and special cases. Production files remain below 200 lines.

## TDD evidence

RED requires semantic f-string parser tests to fail at the current reserved
syntax error and root API tests to fail on missing exports. GREEN requires the
mirrored parser suite and API contract. DONE requires the complete quality gate
and synchronized READMEs and progress ledger.
