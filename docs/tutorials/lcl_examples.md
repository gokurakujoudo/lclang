# LCL examples gallery

LCL is a versioned, expression-only language: every example below produces a
value or raises a value. Its spelling is intentionally familiar to Python users,
but pylcl uses its own lexer, AST, parser, and async interpreter—never Python
`eval`, `exec`, or Python-AST compilation.

This gallery moves from small expressions to functional programs. Every `lcl`
fence is parser-checked by the test suite. For formal precedence and edge cases,
see the [complete V1 syntax](../lcl-lang.md).

## Literals

Integers support decimal, binary, octal, hexadecimal, and underscore grouping.
Floats support decimal fractions and exponents.

```lcl
0b1010 + 0o12 + 0xA + 1_000 + 6.25e-2
```

Booleans and null have lowercase configuration spellings as well as their
Python-compatible spellings.

```lcl
[true, false, none, True, False, None]
```

Strings may be single-, double-, or triple-quoted. Adjacent strings concatenate;
raw strings keep backslashes. Bytes use `b`, `br`, or `rb` and cannot contain
Unicode escapes.

```lcl
"hello, " "world" + r"\literal"
```

```lcl
b"header" b"\x00"
```

Formatted strings accept expressions, debug `=`, conversions, alignment, and
nested format specifications.

```lcl
f"user={user.name!r:>12} count={len(items):0{width}d}"
```

Comments begin with `#` outside a literal. An expression may span physical lines
without a continuation marker when parsed directly (the `.lclcfg` container has
its own explicit-continuation rule).

## Operators and decisions

Arithmetic follows familiar precedence. V1 includes `+ - * ** / // % @`, unary
`+ - ~`, shifts, and bitwise `& ^ |`. The host values decide which operations
their protocols support.

```lcl
-base ** 2 + count * 4 // 3 % 2
```

```lcl
(flags & mask) | (extra << 2) ^ disabled
```

```lcl
left_matrix @ right_matrix
```

Comparisons chain and evaluate the shared middle operand once. Membership and
identity operators are included.

```lcl
0 < score <= 100 and role in allowed_roles and value is not none
```

`and` and `or` short-circuit and return operand values; `not` returns a boolean.

```lcl
enabled and selected or fallback
```

Null coalescing (`??`) falls back only for `None`, not for `0`, `false`, or an
empty collection.

```lcl
request_value ?? environment_value ?? "default"
```

The conditional form is an expression and associates from the right.

```lcl
"large" if size > 100 else "medium" if size > 10 else "small"
```

<!-- pylcl-exec -->
```python
import pylcl

assert pylcl.evaluate_sync("2 + 3 * 4") == 14
assert pylcl.evaluate_sync(
    "cached ?? fallback",
    {"cached": None, "fallback": 42},
) == 42
assert pylcl.evaluate_sync(
    "10 > value > 2",
    {"value": 5},
) is True
```

## Attributes, indexing, and calls

Attribute access uses `.`, while safe attribute `?.` returns `None` only when
the receiver itself is `None`. It does not hide a missing attribute on a real
object.

```lcl
user?.profile?.display_name ?? "anonymous"
```

Subscriptions accept an index, a tuple of indices, or a slice.

```lcl
matrix[1, 2] + items[1:8:2][0]
```

Calls evaluate left-to-right. `*` expands an iterable and `**` expands a mapping
with string keys. Explicit keyword names cannot repeat.

```lcl
render(document, *sections, theme="dark", **options)
```

There is no `await` keyword. Resolver values, call results, operations, iterator
steps, container children, and context protocols are awaited automatically.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl


async def double(value: int) -> int:
    await asyncio.sleep(0)
    return value * 2


async def main() -> None:
    expression = pylcl.parse_expression("double(value) + 1")
    assert await pylcl.evaluate(expression, {"double": double, "value": 21}) == 43


asyncio.run(main())
```

## Collection displays

Parentheses group or create tuples. A one-item tuple needs its comma.

```lcl
("only",)
```

Lists, tuples, and sets accept `*` unpacking.

```lcl
[0, *prefix, value, *suffix]
```

```lcl
{*primary_tags, "featured", *secondary_tags}
```

An empty `{}` is a dictionary; a non-key item makes a set. Dictionaries accept
`**` unpacking, with later entries winning.

```lcl
{**defaults, "enabled": true, **overrides}
```

## Comprehensions and generators

List, set, and dictionary comprehensions can contain repeated `for` and `if`
clauses. Each target is one identifier in V1.

```lcl
[value * 2 for value in values if value > 0]
```

```lcl
{word.lower() for word in words if word}
```

```lcl
{item.id: item.name for item in items if item?.enabled ?? false}
```

Clauses nest left-to-right, and later clauses can use earlier targets.

```lcl
[(x, y) for x in xs if x > 0 for y in ys if y % x == 0]
```

PEP 798-style starred heads flatten iterables or mappings during a
comprehension.

```lcl
[*group for group in groups]
```

```lcl
{**mapping for mapping in mappings}
```

Parenthesized comprehension syntax produces a lazy async generator. Its source
is not iterated until a consumer asks for items.

```lcl
(transform(item) for item in source if accept(item))
```

## Functions and closures

Functions use `def (parameters): expression` and are values. They support
positional parameters, creation-time defaults, variadic positional parameters,
keyword-only parameters after `*args`, and variadic keyword parameters.

```lcl
def (value, scale=2, *extras, clamp=true, **options): value * scale
```

Functions capture their defining resolver, so returning a function creates a
lexical closure.

```lcl
def (offset): def (value): offset + value
```

Defaults evaluate once when the function value is created, not once per call.
Calls are async even when every operation inside is synchronous.

## Definition context and compact dates

Inside a Module or `.lclcfg` definition, the fundamental `lhs()` function
returns that definition's name. It is useful for records that should carry the
key used to define them.

```lcl
{"name": lhs(), "enabled": true}
```

`lhs()` requires Frame definition evaluation; it is unavailable to a standalone
`evaluate` call because that expression has no left-hand name.

Function bodies retain their defining owner. With `x` defined as
`def (a): f"{a}-{lhs()}"` and `y` defined as `x(lhs())`, evaluation returns
`"y-x"`: the argument belongs to `y`, while the body belongs to `x`.

The builtin `parse_ymd` and `to_ymd` functions convert strict, locale-free
`YYYYMMDD` strings and `datetime.date` values.

```lcl
to_ymd(parse_ymd("20240229"))
```

## Assertions, deliberate failures, and recovery

`assert(condition)` returns the truthy condition. Its optional message is
evaluated only on failure.

```lcl
assert(port > 0, f"invalid port: {port}")
```

`raise(value)` deliberately creates an `LclEvaluationError` with source
information.

```lcl
raise("configuration is incomplete")
```

## Try and with

A `try` form is one expression. Typed handlers inspect the public failure and
its cause chain; a bare handler catches ordinary `Exception` and must be last.
`finally` always runs and may replace the pending result or failure.

```lcl
try: load() except LclNameError as error: fallback(error) except: none finally: audit()
```

A `with` form enters managers left-to-right and exits right-to-left. Async
protocols are preferred, sync protocols are supported, and earlier `as`
bindings are visible to later manager expressions.

```lcl
with source() as rows, transaction(rows) as tx: tx.write([transform(row) for row in rows])
```

These are expression forms, so they can be nested inside calls, collections,
functions, and conditions.

## Hard example: fixed points under eager evaluation

Directly re-entering the identical LCL function value in one task is rejected.
That guard catches accidental self-recursion and produces a structured error.
Recursion is still expressible functionally: an eta-expanded fixed-point
combinator produces a fresh deferred closure for the next recursive step.

### Unary Y combinator

This eager-language Y combinator accepts a one-argument recursive function
builder. The small `def (value): ...` wrapper is the eta expansion that delays
the next self-application until the recursive call is actually needed.

```lcl
def (f): (def (x): f(def (value): x(x)(value)))(def (x): f(def (value): x(x)(value)))
```

Factorial becomes a non-recursive builder that receives its recursive operation
as `again`:

```lcl
Y(def (again): def (n): 1 if n <= 1 else n * again(n - 1))
```

The same Y combinator can derive Fibonacci:

```lcl
Y(def (again): def (n): n if n <= 1 else again(n - 1) + again(n - 2))
```

### Variadic Z combinator

Using `*args` makes the delayed recursive operation reusable for functions of
different arities.

```lcl
def (f): (def (x): f(def (*args): x(x)(*args)))(def (x): f(def (*args): x(x)(*args)))
```

## Hard example: recursive Quicksort

Quicksort demonstrates several features together: the variadic Z combinator,
closures, conditionals, slicing, comprehensions, comparisons, list displays,
concatenation, and duplicate preservation.

```lcl
Z(def (again): def (items): [] if not items else again([item for item in items[1:] if item < items[0]]) + [items[0]] + again([item for item in items[1:] if item >= items[0]]))
```

The recursive examples below are executed by the documentation test suite.

<!-- pylcl-exec -->
```python
import asyncio

import pylcl

Y_SOURCE = (
    "def (f): (def (x): f(def (value): x(x)(value)))"
    "(def (x): f(def (value): x(x)(value)))"
)
Z_SOURCE = (
    "def (f): (def (x): f(def (*args): x(x)(*args)))"
    "(def (x): f(def (*args): x(x)(*args)))"
)


async def main() -> None:
    y = await pylcl.evaluate(pylcl.parse_expression(Y_SOURCE))
    factorial = await pylcl.evaluate(
        pylcl.parse_expression(
            "Y(def (again): def (n): 1 if n <= 1 else n * again(n - 1))"
        ),
        {"Y": y},
    )
    fibonacci = await pylcl.evaluate(
        pylcl.parse_expression(
            "Y(def (again): def (n): n if n <= 1 else "
            "again(n - 1) + again(n - 2))"
        ),
        {"Y": y},
    )
    assert await pylcl.evaluate(
        pylcl.parse_expression("factorial(6)"), {"factorial": factorial}
    ) == 720
    assert await pylcl.evaluate(
        pylcl.parse_expression("fibonacci(10)"), {"fibonacci": fibonacci}
    ) == 55

    z = await pylcl.evaluate(pylcl.parse_expression(Z_SOURCE))
    quicksort = await pylcl.evaluate(
        pylcl.parse_expression(
            "Z(def (again): def (items): [] if not items else "
            "again([item for item in items[1:] if item < items[0]]) + "
            "[items[0]] + "
            "again([item for item in items[1:] if item >= items[0]]))"
        ),
        {"Z": z},
    )
    assert await pylcl.evaluate(
        pylcl.parse_expression("sort(values)"),
        {"sort": quicksort, "values": [7, 2, 9, 2, -1, 5]},
    ) == [-1, 2, 2, 5, 7, 9]


asyncio.run(main())
```

## What LCL intentionally leaves out

LCL V1 has no assignment statements, mutation statements, classes, imports,
loops, `lambda`, explicit `await`, `yield`, or Python code injection. Use
expressions, comprehensions, `def`, `try`, `with`, reviewed host values, and
`.lclcfg` definitions instead.

Continue with [configuration files](config_file.md) to give these expressions
names and compose them across files.
