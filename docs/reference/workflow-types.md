# Workflow variable types and explicit boxes

`define_variable[T](name)` captures a Python annotation and gives `.quote` the
static type `T`. It does not turn a Frame into a schema validator. A quote is a
definition marker; use the actual value only after argument materialization.

## Choose a declaration

| Type family | Recommended declaration | Runtime behavior |
| --- | --- | --- |
| Scalars and application classes | `define_variable[int]`, `define_variable[Path]` | Preserve the object; no coercion. |
| Containers and abstract collections | `define_variable[list[str]]`, `define_variable[Collection[str]]` | Preserve containers and elements by reference. |
| Optional and union values | `define_variable[str \| None]` | Preserve the chosen value, including `None`. |
| Callbacks | `define_variable[Callable[[str], int]]` | Retain the callable; invocation is explicit. |
| Protocol values | `define_variable[Reader]` | No implicit structural validation. |
| Concrete or generic dataclasses | `define_variable[Options]`, `define_variable[Batch[str]]` | Whole mappings require an exactly matching record annotation; scopes construct that record. |
| Open values | `define_variable[object]` or `define_variable[Any]` | Prefer a narrower type when known. |
| Null-only values | `define_variable[None]` | `None` is a value, not a missing binding. |

Container elements, `Literal` constraints and structural typing rules are not
recursively checked. Validate external data in application code.

<!-- lclang-doc-exec -->
```python
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, assert_type

from lclang.workflow import define_variable


class Reader(Protocol):
    def read(self) -> str: ...


@dataclass
class Batch[T]:
    items: list[T]


assert_type(define_variable[Path]("path").quote, Path)
assert_type(define_variable[Collection[str]]("items").quote, Collection[str])
assert_type(define_variable[str | None]("optional").quote, str | None)
assert_type(define_variable[Callable[[str], int]]("callback").quote, Callable[[str], int])
assert_type(define_variable[Reader]("reader").quote, Reader)
assert_type(define_variable[object]("opaque").quote, object)
assert_type(define_variable[Any]("legacy").quote, Any)
assert_type(define_variable[None]("null").quote, None)
batch = define_variable[Batch[str]]("batch")
assert_type(batch.quote, Batch[str])
assert batch.value_type == Batch[str]
```

Use direct declarations for independent inputs. Generic subscription accepts
more annotation forms than `.field(name, field_type)`. Avoid wrappers when a
direct variable already expresses the data flow.

## Project concrete wrapper types

`.field()` keeps `type[T]` and zero runtime dependencies. It verifies the field
name and exact declared annotation. Ordinary classes and suitable parameterized
concrete types work directly. Bare Protocol classes and union expressions are
not a portable strict-typing interface for this parameter.

`ValueBox[T]` gives an optional value, collection or Protocol a concrete wrapper.
`CallableBox[P, R]` forwards a callback with its regular callable signature.
Both expose only one data field, `value`, and are available from `lclang.utils`.
Declare the wrapper in the source record as well as the projection.

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from lclang import define_frame
from lclang.utils import CallableBox, ValueBox
from lclang.workflow import (
    ExecutionStatusManager, TaskContext, WorkflowExecutionContext,
    define_task, define_variable, define_workflow,
)


@dataclass
class Settings:
    rename: ValueBox[str | None]
    parse: CallableBox[[str], int]


async def use_settings(
    context: TaskContext, args: Settings, status_mgr: ExecutionStatusManager,
) -> Settings:
    assert args.rename.value is None
    assert args.parse("17") == 17
    return args


async def main() -> None:
    source = define_variable[Settings]("settings")
    output = define_variable[ValueBox[str | None]]("result")
    mapping = Settings(
        source.field("rename", ValueBox[str | None]).quote,
        source.field("parse", CallableBox[[str], int]).quote,
    )
    task = define_task(
        "use", "Use settings", task_action=use_settings, args_mapping=mapping,
        outputs_mapping=Settings(output.quote, CallableBox(int)),
    )
    async with define_frame(preset={"settings.rename": None, "settings.parse": int}) as frame:
        result = await define_workflow("Settings", task).execute(WorkflowExecutionContext(
            False, date(2026, 9, 23), False, logging.getLogger("boxes-example"), frame,
        ))
        assert await frame.get("result") is None
        assert await frame.get("settings.parse") is int
        assert result.task_outputs["use"].rename.value is None


asyncio.run(main())
```

Selected projections box raw scope values. Only `result` is an output quote,
so it publishes its payload `None`. The literal callback in the output template
is unmapped. The returned action record retains its boxes.

## Preserve Protocol contracts explicitly

A box never checks `isinstance(payload, Protocol)`. Hold a non-callable Protocol
in `ValueBox[ProtocolType]` and use `.value`. For callable Protocols with overloads,
keywords or additional members, use a named subclass with explicit delegation.

<!-- lclang-doc-exec -->
```python
from typing import Protocol

from lclang.utils import CallableBox, ValueBox


class Rule(Protocol):
    def __call__(self, text: str, *, upper: bool = False) -> str: ...


class RuleBox(ValueBox[Rule]):
    def __call__(self, text: str, *, upper: bool = False) -> str:
        return self.value(text, upper=upper)


def format_text(text: str, *, upper: bool = False) -> str:
    return text.upper() if upper else text


assert RuleBox(format_text)("hello", upper=True) == "HELLO"
assert CallableBox(format_text)("hello", upper=True) == "HELLO"
shared = ["a", "b"]
assert ValueBox(shared).value is shared
```

ParamSpec preserves the ordinary callback's keyword signature. The named
subclass also gives the Protocol a concrete identity. Add overloads and other
members explicitly when needed; no universal Protocol proxy is generated.

## Conversion cost and unsupported uses

- Reading one explicitly boxed variable or projection normally allocates one
  wrapper holding one reference: constant work and storage relative to payload
  size. Re-reading may allocate another wrapper; the payload remains shared.
- Matching boxes are reused. Incompatible boxes are rejected, not double-boxed.
  Only the outer wrapper type is checked; payload annotations are not validators.
- Publishing an explicitly boxed output reads `.value` once. There is no deep
  copy, container walk or mutation. Returned task outputs keep their wrappers.
- Callable boxes add one ordinary Python call, with no task, implicit await,
  resource ownership or exception translation.
- Ordinary records, whole-record contents and container elements are not searched
  for wrappers. For raw scoped fields requiring boxes, use explicit projections
  as above. Whole-record quotes do not recursively box their fields.

Non-dataclass whole mappings, output projections, projections from union or
non-record roots, mismatched field annotations and cyclic templates are
unsupported. A bare non-runtime-checkable Protocol projection can fail the
existing outer-shape check even if static errors are bypassed; use boxes.
`TypedDict`, forward-reference strings and special typing forms are not a
general runtime validation language. Resolve record annotations normally and
validate external data explicitly. See [mapping best practices](workflow-mappings.md).
