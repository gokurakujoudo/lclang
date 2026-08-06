# M023: try and with control forms

## Goal

Add expression-oriented error recovery, finalization, and context management
without introducing a statement execution engine.

## Syntax

- Try: `try: body except Type as name: handler finally: cleanup`
- With: `with context as name, other_context: body`

Try permits multiple handlers, an optional final bare handler, and optional
`finally`. At least one handler or `finally` is required. With requires at least
one item; each `as` target is a simple non-empty name.

## Module and test layout

- `pylcl/ast/control_forms.py` and its mirrored AST test own with items, with
  forms, except handlers, and try forms.
- `pylcl/lang/parser/control_forms.py` and its mirror own clause boundaries,
  target validation, ordering, and complete-expression bodies.
- `pratt.py` checks control forms at the same complete-expression boundary as
  M022 forms.

## Contract

- Except handlers preserve optional exception expression, optional bound name,
  and handler body. `as` requires an exception expression and a name.
- A bare except handler must be last. Handler bodies and finally body are
  ordinary complete expressions.
- Try children are body, handlers, then optional finalizer. With children are
  item nodes then body; each item contains its context expression only.
- Context managers are entered left-to-right and later exited right-to-left by
  the evaluator; the AST retains source order.
- Missing clauses, colons, names, bodies, invalid bare-handler ordering, and
  trailing unexpected clauses raise source-aware syntax errors.
- Public docstrings satisfy M007 and source files remain below 200 lines.

## TDD evidence

RED must fail because both control-form modules are absent and keywords remain
invalid atoms. GREEN requires both mirrored suites and parser regressions. DONE
requires the complete quality gate and documentation synchronization.
