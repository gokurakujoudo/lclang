# LCL V1 language syntax

LCL V1 is pylcl's versioned, expression-only configuration language. It borrows
familiar Python spellings while using its own lexer, custom immutable AST,
parser, canonical printer, and async interpreter. It never compiles through the
Python AST, `eval`, `exec`, or bytecode.

This guide describes the implemented expression language. The `.lclcfg` file
format planned for 0.2 adds definitions and includes around these expressions;
it does not change the V1 expression grammar.

## Lexical structure

Source is Unicode text. Positions use one-based lines/columns and zero-based
Unicode code-point offsets. Spaces, tabs, form feeds, and physical newlines
separate tokens. Newlines are discarded before expression parsing, so a single
expression may span lines without backslashes. A `#` starts a comment through
the physical end of line, except inside a quoted literal or f-string field.

Identifiers follow Python's Unicode `str.isidentifier` rules. These lowercase
words are reserved: `and`, `or`, `not`, `if`, `else`, `for`, `in`, `is`, `true`,
`false`, `none`, `def`, `raise`, `try`, `except`, `finally`, `assert`, `with`,
and `as`. Python-compatible `True`, `False`, and `None` are also accepted.
Canonical printing uses `True`, `False`, and `None`.

<!-- lcl-valid -->
```lcl
total # the expression continues after the ignored comment
```

Punctuation and fixed operators are:

```text
( ) [ ] { } , : . ?. ??
+ - * ** / // % @ << >> & ^ | ~
< <= > >= == != =
```

Bare `=` is only parameter-default or keyword-argument syntax. It is not an
assignment expression.

## Grammar

The following EBNF is explanatory. `expression` permits low-precedence forms;
`nonconditional` excludes an unparenthesized trailing conditional where the
surrounding grammar needs an unambiguous delimiter.

```text
expression       ::= control-form | function-form | raise-form | assert-form
                   | conditional
conditional      ::= coalesce ["if" coalesce "else" conditional]
coalesce         ::= or-expression ["??" coalesce]
or-expression    ::= and-expression {"or" and-expression}
and-expression   ::= not-expression {"and" not-expression}
not-expression   ::= "not" not-expression | comparison
comparison       ::= bit-or {comparison-op bit-or}
comparison-op    ::= "<" | "<=" | ">" | ">=" | "==" | "!="
                   | "in" | "not" "in" | "is" | "is" "not"
bit-or           ::= bit-xor {"|" bit-xor}
bit-xor          ::= bit-and {"^" bit-and}
bit-and          ::= shift {"&" shift}
shift            ::= sum {("<<" | ">>") sum}
sum              ::= product {("+" | "-") product}
product          ::= unary {("*" | "@" | "/" | "//" | "%") unary}
unary            ::= ("+" | "-" | "~") unary | power
power            ::= primary ["**" unary]
primary          ::= atom {attribute | safe-attribute | subscript | call}
```

A top-level comma constructs a tuple. Parentheses group an expression or make
the tuple boundary explicit.

## Operator precedence

From tightest to loosest:

| Level | Syntax | Associativity / behaviour |
|---|---|---|
| Primary | `.`, `?.`, `[]`, `()` | left chained |
| Power | `**` | right associative |
| Unary | `+x`, `-x`, `~x` | power binds inside unary |
| Product | `*`, `@`, `/`, `//`, `%` | left associative |
| Sum | `+`, `-` | left associative |
| Shift | `<<`, `>>` | left associative |
| Bitwise AND/XOR/OR | `&`, `^`, `|` | three separate levels |
| Comparison | `< <= > >= == != in not in is is not` | chained, short-circuit |
| Boolean NOT | `not` | recursive prefix |
| Boolean AND/OR | `and`, then `or` | short-circuit, value preserving |
| Null coalescing | `??` | right associative, checks exactly `None` |
| Conditional | `yes if condition else no` | right associative |
| Forms | `def`, `raise`, `assert`, `try`, `with` | complete-expression forms |

<!-- lcl-valid -->
```lcl
-2 ** 2 + 3 * 4 << 1
```

<!-- lcl-valid -->
```lcl
lower <= value < upper and enabled
```

<!-- lcl-valid -->
```lcl
cached ?? load() ?? fallback
```

<!-- lcl-valid -->
```lcl
primary if ready else backup if available else none
```

`and` and `or` return operand values, not forced booleans. `not` returns a
boolean. Comparisons evaluate the shared middle operand once. `??` evaluates
its right side only when its left value is exactly `None`; false, zero, and
empty collections do not trigger fallback.

## Literals

### Numbers and constants

Integers support decimal, binary (`0b`), octal (`0o`), hexadecimal (`0x`), and
valid underscore separators. Decimal floats support fractional and exponent
forms. Complex numbers are not part of V1.

<!-- lcl-valid -->
```lcl
0b1010 + 0o12 + 0xA + 1_000 + 6.25e-2
```

<!-- lcl-valid -->
```lcl
[true, false, none, True, False, None]
```

### Text, bytes, and raw literals

Single, double, and triple quotes are supported. Prefixes are case-insensitive:
`r` makes raw text, `b` makes bytes, and `br`/`rb` make raw bytes. Ordinary text
escapes include common single-character escapes, octal, `\xhh`, `\uhhhh`,
`\Uhhhhhhhh`, and named Unicode escapes. Bytes reject Unicode escapes and
non-ASCII source characters. Physical newlines require triple quotes.

Adjacent literals of the same kind concatenate during parsing. Text and bytes
cannot be mixed.

<!-- lcl-valid -->
```lcl
"hello, " "world" + r"\literal"
```

<!-- lcl-valid -->
```lcl
b"header" b"\x00"
```

### Formatted strings

`f`, `fr`, and `rf` prefixes work with every text quote style. Use `{{` and
`}}` for literal braces. A field contains a non-empty LCL expression, optional
debug `=`, optional `!s`/`!r`/`!a`, and optional format spec. Format specs may
contain nested fields. Backslashes and comments are forbidden inside field
expression source.

<!-- lcl-valid -->
```lcl
f"user={user.name!r:>12} count={len(items)}"
```

## Primaries and calls

Ordinary attribute access uses the host object's `getattr` protocol. Safe
attribute `?.` returns `None` only when its receiver is exactly `None`; it does
not suppress a missing attribute or descriptor failure.

Subscriptions accept one index, a tuple of indices, or a slice. Calls evaluate
the callable first and arguments left-to-right. `*` expands sync/async iterables;
`**` requires a mapping with string keys. Positional arguments must precede
explicit keyword or keyword-unpack arguments. Explicit keyword names cannot
repeat.

<!-- lcl-valid -->
```lcl
user?.profile?.display_name ?? "anonymous"
```

<!-- lcl-valid -->
```lcl
matrix[1, 2] + items[1:8:2][0]
```

<!-- lcl-valid -->
```lcl
render(document, *sections, theme="dark", **options)
```

Every resolver result, operation result, call result, context result, and
container child is automatically awaited when it is awaitable. There is no
explicit `await` keyword in LCL.

## Collections and comprehensions

Displays use Python-like delimiters:

- `()` is the empty tuple; `(value,)` is a one-item tuple; `(value)` groups.
- `[]` is a list; `{}` is an empty dictionary; `{value}` is a set.
- `*iterable` unpacks in tuple/list/set displays.
- `**mapping` unpacks in dictionary displays.
- Mixing set and dictionary entries is a syntax error.

<!-- lcl-valid -->
```lcl
("only",)
```

<!-- lcl-valid -->
```lcl
[0, *prefix, value, *suffix]
```

<!-- lcl-valid -->
```lcl
{**defaults, "enabled": true, **overrides}
```

Generator, list, set, and dictionary comprehensions support repeated `for` and
`if` clauses. Each target is one identifier; destructuring targets are outside
V1. PEP 798-style `*` heads work for list/set comprehensions and `**` heads for
dictionary comprehensions.

<!-- lcl-valid -->
```lcl
[value * 2 for value in values if value > 0]
```

<!-- lcl-valid -->
```lcl
(pair for left in lefts for pair in combine(left) if pair)
```

<!-- lcl-valid -->
```lcl
{**mapping for mapping in mappings}
```

The first iterable of a materialized comprehension evaluates eagerly; later
iterables, filters, and output are conditional. Generator dependencies are
deferred until iteration. Targets bind only after their iterable and remain in
scope for later clauses and the head.

## Function and control forms

All forms are expressions and return values (or raise). They can appear as a
definition value, collection child, call argument, or parenthesized subexpression.

### Functions

```text
function-form ::= "def" "(" [parameter {"," parameter} [","]] ")"
                  ":" expression
parameter     ::= name ["=" nonconditional]
                | "*" name
                | name ["=" nonconditional]   # after *name: keyword-only
                | "**" name
```

Defaults evaluate once when the function value is created. The body uses the
defining lexical resolver. Calls are async and argument binding supports
positional, defaulted, variadic positional, keyword-only-after-`*name`, and
variadic keyword parameters. Recursive re-entry of the same LCL function in one
task is prohibited; concurrent calls in different tasks are independent.

<!-- lcl-valid -->
```lcl
def (value, scale=2, *extras, clamp=true, **options): value * scale
```

### Deliberate failures and assertions

`raise(value)` raises a source-aware `LclEvaluationError`; a BaseException value
becomes its cause. `assert(condition)` returns the truthy condition value.
`assert(condition, message)` evaluates the message only on a falsey condition,
then raises `LclEvaluationError`.

<!-- lcl-valid -->
```lcl
raise("configuration is incomplete")
```

<!-- lcl-valid -->
```lcl
assert(port > 0, f"invalid port: {port}")
```

### Try expressions

```text
try-form ::= "try" ":" expression
             {"except" [nonconditional ["as" name]] ":" expression}
             ["finally" ":" expression]
```

At least one `except` or `finally` is required. Handlers run in source order. A
bare handler catches ordinary `Exception` and must be last. Typed handlers use
`isinstance` against the public error and its cause chain. An `as` binding exists
only in its handler. `finally` always evaluates and its failure replaces a
pending result/failure. Direct `BaseException` values such as cancellation,
`KeyboardInterrupt`, and `SystemExit` are not caught by handlers.

<!-- lcl-valid -->
```lcl
try: load() except LclNameError as error: fallback except: none finally: audit()
```

### With expressions

```text
with-form ::= "with" with-item {"," with-item} ":" expression
with-item ::= nonconditional ["as" name]
```

Managers enter left-to-right and exit right-to-left. Async protocols are
preferred; sync protocol results are also auto-awaited. Earlier `as` bindings
are visible to later manager expressions and the body. Truthy exit results
suppress the active failure and make the expression return `None`.

<!-- lcl-valid -->
```lcl
with open_resource() as resource, transaction(resource) as tx: tx.use(resource)
```

## Composite examples

These examples combine multiple grammar families and are parser-checked as a
separate composite-complex acceptance set.

<!-- lcl-composite -->
```lcl
def (items, *extras, limit=10, **options): [*items, *extras][:limit]
```

<!-- lcl-composite -->
```lcl
try: assert(value > 0, "positive required") except LclEvaluationError as error: fallback(error) finally: audit()
```

<!-- lcl-composite -->
```lcl
with source() as rows, transaction() as tx: tx.write([transform(row) for row in rows if row?.enabled ?? false])
```

## Evaluation semantics

Evaluation is async-first and left-to-right except documented short circuits,
conditional branches, lazy generators/functions, and cleanup unwinding. Host
protocols provide arithmetic, comparison, attributes, indexing, calls,
iteration, formatting, and context management. Ordinary host `Exception`
failures are wrapped once as source-aware `LclEvaluationError`; existing LCL
errors pass through.

Runtime Frames add lazy per-name success/failure caching, one owner task per
name, cycle detection, waiter cancellation isolation, task-local resource
limits, explicit atomic recalculation, dependency snapshots, and deterministic
close. Recalculation never invalidates dependants. LCL is trusted configuration,
not a security sandbox: host values and callables may have ordinary Python side
effects or blocking behaviour.

## Rainy cases and exceptions

The marked examples below are deliberately malformed and are continuously
checked to raise `LclSyntaxError` with a source span.

<!-- lcl-invalid -->
```lcl
1 +
```

<!-- lcl-invalid -->
```lcl
[1, 2
```

<!-- lcl-invalid -->
```lcl
{"set", "key": 2}
```

<!-- lcl-invalid -->
```lcl
[**mapping]
```

<!-- lcl-invalid -->
```lcl
call(option=1, 2)
```

<!-- lcl-invalid -->
```lcl
def (x=1, y): x + y
```

<!-- lcl-invalid -->
```lcl
def (x, x): x
```

<!-- lcl-invalid -->
```lcl
raise "boom"
```

<!-- lcl-invalid -->
```lcl
assert(true
```

<!-- lcl-invalid -->
```lcl
try: value
```

<!-- lcl-invalid -->
```lcl
try: value except: 0 except Error: 1
```

<!-- lcl-invalid -->
```lcl
with manager as: value
```

<!-- lcl-invalid -->
```lcl
f"{}"
```

<!-- lcl-invalid -->
```lcl
"text" b"bytes"
```

Runtime rainy cases use structured public exceptions:

| Situation | Exception / behaviour |
|---|---|
| Unknown resolver name | `LclNameError` with requesting span |
| Unsupported host operation/protocol failure | wrapped `LclEvaluationError` with cause |
| `raise` or failed `assert` | source-aware `LclEvaluationError` |
| Frame dependency cycle | `LclCircularDependencyError` with ordered path |
| Evaluation budget exceeded | `LclEvaluationError` at offending AST span |
| Request after close begins | `LclClosedFrameError` |
| Direct cancellation/BaseException | propagates unwrapped after required cleanup |
| Missing ordinary attribute after `?.` on non-None | normal failure; not suppressed |
| Duplicate `**` keyword at runtime | wrapped `TypeError` cause |

## Unsupported Python syntax

V1 deliberately excludes statements and Python compilation semantics:

- assignment statements, annotated assignment, `:=`, and augmented assignment;
- `lambda`, `async def`, explicit `await`, `yield`, and `yield from`;
- `import`, `from`, `class`, `match`, loops, statement `if`, and statement `try`;
- list/set/dict target destructuring and function recursion;
- complex literals, template strings, and bytes f-strings;
- arbitrary code loading, Python AST injection, and implicit module access.

Use LCL's `def (...) : expression`, expression-form `try`/`with`, host-provided
reviewed Presets, and explicit application APIs instead.
