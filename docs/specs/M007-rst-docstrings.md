# M007: English rST production docstrings

## Goal

Make production API documentation complete enough to use without reading
implementation code and keep that standard enforceable across later sessions.

## Contract

- Every production module, class, function, and method, including private and
  nested declarations, has an English docstring.
- Docstrings use rST field lists and directives rather than Google or NumPy
  section syntax.
- Every callable documents each non-`self`/`cls` parameter with
  `:param name:`, and documents its result with `:returns:` unless no return or return type is `None`.
- Every intentional public exception has a matching `:raises ExceptionType:`.
- Dataclass-style values, including private values, document every constructor field with
  `:param field:`.
- A class or callable uses `.. note::` only when it documents a meaningful edge
  case, lifecycle constraint, immutability rule, or other non-obvious behaviour.
  Boilerplate notes and statements that there is no special behaviour are
  prohibited.
- Private implementation helpers follow the same complete English/rST contract;
  their prose explains their responsibility and is not merely a name restatement.
- Tests retain short behavioural docstrings; their arguments are fixtures or
  parametrization machinery rather than public API.

## Automated gate

`scripts/check_project.py` parses production modules, validates rST fields for
all functions, methods, and annotated value-class fields, and reports the
exact declaration and missing field. Its own mirrored unit tests cover valid
contracts and independent failures.

## TDD evidence

RED adds structural tests which the current checker cannot satisfy. GREEN
requires a checker implementation and a complete production-docstring audit.
DONE requires the full quality gate before M015 resumes.
