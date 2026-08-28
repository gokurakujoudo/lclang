# The LCL language

LCL is expression-only and familiar to Python readers, but it is not Python
source. lclang tokenizes, parses, prints, and interprets its own immutable AST.
Every complete expression produces a value or raises a value.

## What you will learn

- the core literal, collection, operator, and access forms;
- how conditionals, null coalescing, and safe attributes express policy;
- how comprehensions and arrow functions build richer transformations;
- which Python statement forms are deliberately absent.

## Core expression families

| Need | LCL form | Example result |
| --- | --- | --- |
| Arithmetic | `price * quantity` | `24` |
| Conditional | `a if enabled else b` | one selected branch |
| Null fallback | `value ?? default` | first non-`None` value |
| Safe attribute | `profile?.name` | `None` when profile is `None` |
| Collection | `[a, b]`, `{key: value}` | list or dictionary |
| Record | `{name=value}` | immutable attribute value |
| Slice | `items[1:4]` | selected range |
| Function | `(x, scale=2) -> x * scale` | lexical callable |
| Comprehension | `[f(x) for x in xs if keep(x)]` | transformed list |

Boolean operators short-circuit. Conditional expressions evaluate only the
selected branch. This matters when the skipped branch is expensive or would
fail for the current input.

## Combine safe access, fallback, and formatting

The host may provide an object or `None`. Safe attribute access handles the
missing object, `??` supplies a fallback, and an f-string formats the result.

<!-- lclang-tutorial-exec -->
```python
from types import SimpleNamespace

import lclang

expression = 'f"Hello, {profile?.display_name ?? fallback}!"'

known = lclang.evaluate_sync(
    expression,
    {"profile": SimpleNamespace(display_name="Ada"), "fallback": "friend"},
)
anonymous = lclang.evaluate_sync(
    expression,
    {"profile": None, "fallback": "friend"},
)

assert known == "Hello, Ada!"
assert anonymous == "Hello, friend!"
```

For `known`, safe access obtains `Ada`, so `??` never evaluates the fallback.
For `anonymous`, accessing through `None` produces `None`, which makes `??`
select `friend`. The same f-string then wraps the selected name in the two
asserted greetings.

`?.` suppresses only access on `None`. It does not hide a missing attribute on
a real object. `??` selects its right side only when the left result is `None`;
false, zero, and empty text remain valid values.

## Build an immutable record with transformed values

This example filters even values, calls a local arrow function, sorts the
result through a supplied host function, and returns both details and a total
as named fields.

<!-- lclang-tutorial-exec -->
```python
import lclang

result = lclang.evaluate_sync(
    "{"
    "squares=sorted([(value -> value * value)(item) "
    "for item in values if item % 2 == 0]), "
    "total=sum([(value -> value * value)(item) "
    "for item in values if item % 2 == 0])"
    "}",
    {
        "values": [5, 2, 4, 3],
        "sorted": sorted,
        "sum": sum,
    },
)

assert isinstance(result, lclang.LclRecord)
assert result.squares == [4, 16]
assert result.total == 20
assert lclang.evaluate_sync("{value=total}.value", {"total": result.total}) == 20
```

The comprehension rejects `5` and `3` because they are odd. The arrow function
squares `2` and `4`, `sorted` orders those values as `[4, 16]`, and the second
comprehension feeds the same values to `sum`, producing `20`. The LCL record
creates both fields eagerly; Python reads them through `result.squares` and
`result.total`, while the final assertion demonstrates the same dotted access
inside LCL.

Arrow functions use `() -> expression`, `name -> expression`, or
`(parameters) -> expression`. They support defaults, keyword calls, lexical
closures, and deferred bodies. A generator expression stays lazy; list, set,
and dictionary comprehensions materialize results.

## Build and inspect syntax without running it

Canonical printing is useful for formatters, diagnostics, and code review.

<!-- lclang-tutorial-exec -->
```python
import lclang

node = lclang.parse_expression("(base+tax)*quantity")
source = lclang.to_source(node)

assert source == "(base + tax) * quantity"
assert lclang.evaluate_sync(
    node,
    {"base": 8, "tax": 2, "quantity": 3},
) == 30
```

The printer retains the parentheses because addition must occur before
multiplication. During evaluation, `base + tax` becomes `10`, then `quantity`
scales it to `30`; both the normalized syntax and the value are asserted.

## Deliberate boundaries

LCL excludes assignment statements, imports, classes, loops, `lambda`, direct
`await`, and Python AST injection. Use expressions, comprehensions, arrow
functions, expression-form `try` and `with`, and narrow host capabilities.
Those constraints keep configuration recognizable as configuration while the
available expression forms still support complex trusted policy.

For the exact grammar, precedence table, control forms, and rainy cases, use
the [language reference](../reference/language.md).

[Previous: Modules and Frames](02-modules-and-frames.md) | [Next: Configuration files](04-configuration-files.md)
