# M022: function, raise, and assert forms

## Goal

Add explicit expression forms for anonymous functions, deliberate errors, and
assertions without introducing statements or Python execution machinery.

## Syntax

- Function: `def (x, y=default, *args, **kwargs): body`
- Raise: `raise(value)`
- Assert: `assert(condition)` or `assert(condition, message)`

The call-like delimiters on raise/assert make their message boundaries
unambiguous inside displays and calls. Function recursion remains a runtime
error even if a function is later bound to a name.

## Module and test layout

- `pylcl/ast/forms.py` and `tests/ast/test_forms.py` own parameter kinds and
  immutable function/raise/assert node values.
- `pylcl/lang/parser/forms.py` and its mirror own keyword recognition,
  parameter validation, delimiters, and body parsing.
- `pratt.py` delegates at the complete-expression boundary; grouping therefore
  permits forms wherever an atom can contain a complete expression.

## Contract

- Parameters preserve positional, keyword-only, variadic positional, and
  variadic keyword kinds plus optional default expressions.
- Names are unique. A required positional parameter cannot follow a defaulted
  positional parameter; no parameter follows `**kwargs`; variadic parameters
  cannot have defaults.
- Function children are parameters then body; parameter children contain only
  an optional default.
- Raise has exactly one value. Assert has one condition and an optional message.
- Missing names, values, delimiters, body, invalid ordering, and duplicates
  raise source-aware `LclSyntaxError`.
- Forms bind as complete expressions; use parentheses before applying ordinary
  primary or binary syntax to a form.
- Public docstrings satisfy M007; no Python AST, `eval`, or `exec` is used.

## TDD evidence

RED must fail because both form modules are absent and keywords are invalid
atoms. GREEN requires both mirrored suites and parser regressions. DONE requires
the complete quality gate and documentation synchronization.
