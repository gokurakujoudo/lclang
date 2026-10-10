# Errors and inspection

Computed configuration needs diagnostics that explain more than a final wrong
value. lclang keeps source spans, variable evaluation stacks, cache state,
definition owners, and dependency structure available through public values.

## What you will learn

- how syntax and evaluation failures differ;
- how variable stacks identify the route to a failure;
- how `inspect_variable` explains a value without evaluating it;
- how inspection changes after a value becomes cached.

## Preserve structured failures

Parsing fails before a Frame exists. Evaluation failures retain the nested
definition route and the original host exception as their cause.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang import (
    LclEvaluationError,
    LclSyntaxError,
    define_frame,
    define_module,
    parse_expression,
)


async def main() -> None:
    try:
        parse_expression("1 +")
    except LclSyntaxError as error:
        assert error.span is not None
        assert "expected an expression" in str(error)
    else:
        raise AssertionError("malformed syntax was accepted")

    def divide(left: int, right: int) -> float:
        return left / right

    module = define_module(
        "calculation",
        {"ratio": "divide(total, count)", "result": "ratio * 100"},
    )
    async with define_frame(
        module,
        preset={"divide": divide, "total": 5, "count": 0},
    ) as frame:
        try:
            await frame.get("result")
        except LclEvaluationError as error:
            assert error.variable_stack == ("result", "ratio")
            assert isinstance(error.__cause__, ZeroDivisionError)
        else:
            raise AssertionError("division failure was not reported")


asyncio.run(main())
```

The incomplete addition fails while parsing, so its error has a source span but
no Frame stack. The second failure starts at `result`, enters `ratio`, and then
calls the host division function with zero. lclang wraps that host exception
once, preserving both the owner route `result -> ratio` and the original
`ZeroDivisionError` cause checked by the assertions.

Catch `lclang.LclError` at an application boundary when one expected family is
useful. Catch narrower subclasses when recovery differs. Cancellation,
`KeyboardInterrupt`, and other base exceptions are not converted into ordinary
language failures.

## Read the failure scene

The diagnostic follows definitions from the requested result to the failing
expression. Values listed beneath a frame were already read by that evaluation;
printing the error does not request missing values or take an unused branch.

<!-- lclang-doc-case: complete-failure-scene -->

<!-- lclang-doc-file: metrics.lclcfg -->
```lclcfg
total: 5
count: 0
ratio: total / count
result: ratio * 100
```

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.config import load_config
from lclang.errors import LclEvaluationError


async def main() -> None:
    config = await load_config("metrics.lclcfg")
    async with config.to_frame() as frame:
        try:
            await frame.get("result")
        except LclEvaluationError as error:
            assert error.variable_stack == ("result", "ratio")
            assert error.evaluation_context[-1].used_values[1].name == "count"
            print(error)


asyncio.run(main())
```

The result is a division failure with both definition frames and the values
`5` and `0`. The caret range identifies the failing expression:

<!-- lclang-doc-output: stdout -->
```text
Error in evaluating result [LCL3001]:
  result at "metrics.lclcfg":4:9
    result: ratio * 100
  ratio at "metrics.lclcfg":3:8
    ratio: total / count
           ^^^^^^^^^^^^^
    total = (int) 5
    count = (int) 0
Cause: ZeroDivisionError: division by zero
```
<!-- /lclang-doc-case -->

Snapshots retain parsed source even after a file changes or the Frame closes.
Cached failures keep their first scene; recalculation creates a new one.
Function calls add frames containing local parameters. Imported definitions
use their actual qualified names, while loading failures retain original child
names. [Configuration composition](17-configuration-composition.md) shows a
nested dynamic-target error with both stacks.

Mark sensitive exact names with `!`. Captured values and expressions then show
`*masked*`; a masked LCL function also protects its body and invocation
parameters. The mask is applied before representation. Derived values still
need their own marker. Single values use a 200-character display budget, and a
broken representation cannot replace the original failure. User messages,
native exception causes, and Python tracebacks remain available as structured
data; treat raw tracebacks as application-controlled logging output.

## Inspect before and after evaluation

Inspection performs lookup and static dependency traversal but never calls,
awaits, caches, or publishes dynamic traces.

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang import define_frame, define_module


async def main() -> None:
    module = define_module(
        "invoice",
        {
            "subtotal": "unit_price * quantity",
            "total": "subtotal + shipping",
        },
    )
    async with define_frame(
        module,
        preset={"unit_price": 8, "quantity": 4, "shipping": 3},
    ) as frame:
        before = frame.inspect_variable("total")
        assert before.status.value == "NotEvaluated"
        assert [str(item.var_name) for item in before.dependencies] == [
            "subtotal",
            "shipping",
        ]
        assert before.dependencies[1].status.value == "ExternalProvided"

        assert await frame.get("total") == 35
        after = frame.inspect_variable("total")
        assert after.status.value == "Cached"
        assert after.current_value == 35
        assert "(Cached) int: 35" in repr(after)


asyncio.run(main())
```

Before evaluation, static analysis finds `subtotal` and `shipping`; lookup also
shows that shipping is an external value, but no result exists for `total`.
The explicit `get` computes `8 * 4 + 3 = 35` and commits it. A second inspection
therefore reports the same definition with `Cached` status and the integer
payload asserted in `repr`.

`tree.to_lines()` renders a compact nested list suitable for logs and issue
reports. Missing leaves remain visible with `LclNameError`. Repeated direct
names collapse within one parent, while a name reached through different
branches remains visible in each branch.

## A safe debugging sequence

1. Call `frame.has(name)` to distinguish absence from failure.
2. Call `frame.get_definition(name)` to see the selected AST without running it.
3. Call `frame.inspect_variable(name)` to explain lookup and static structure.
4. Evaluate only if runtime evidence is needed.
5. Inspect again or read `dependency_snapshot(name)` to compare prediction with
   observed behavior.

This order respects lclang's design: observation should not accidentally cause
the work being diagnosed.

[Previous: Caching and recalculation](06-caching-and-recalculation.md) | [Next: Dependency analysis](08-dependency-analysis.md) | [Return to the series introduction](README.md)
