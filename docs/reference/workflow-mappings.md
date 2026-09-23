# Workflow mapping shapes and best practices

Mappings describe data flow using dataclass structure and `.quote` markers.
A quote is a typed marker while defining a workflow; actions receive its
materialized value. Context tasks follow the same mapping rules.

## Choose the smallest mapping

| Shape | Best use | Input behavior | Output behavior |
| --- | --- | --- | --- |
| `args_mapping=record.quote` | Transfer a complete cohesive record | Preserve a concrete record or construct it from a scope | Publish the record, or its direct fields into an existing scope |
| `Args(source.quote, literal)` | Select independent inputs | Resolve quotes; preserve ordinary literal references | Publish only quoted destinations |
| `Args(Options(source.quote))` | Compose nested inputs | Rebuild dataclass templates recursively | Follow nested fields to explicit targets |
| `Args(options.quote)` | Reuse a complete nested record | Resolve the nested whole-record quote | Publish the nested record at its quoted destination |
| `Args(source.field("name", str).quote)` | Read a declared field | Read-only projection retaining the root dependency | Invalid as an output target |

## From direct to nested data flow

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from lclang import define_frame
from lclang.workflow import (
    ExecutionStatusManager, TaskContext, WorkflowExecutionContext,
    define_task, define_variable, define_workflow,
)


@dataclass
class Options:
    encoding: str = "utf-8"


@dataclass
class Request:
    options: Options
    labels: list[str]


async def echo(
    context: TaskContext, args: Request, status_mgr: ExecutionStatusManager,
) -> Request:
    return args


async def main() -> None:
    source = define_variable[Request]("source")
    target = define_variable[Request]("target")
    encoding = define_variable[str]("encoding", default="ascii")
    options = define_variable[Options]("options")
    published = define_variable[str]("published")
    record = Request(Options("utf-16"), ["shared"])
    direct = define_task(
        "direct", "Transfer a complete record", task_action=echo,
        args_mapping=source.quote, outputs_mapping=target.quote,
    )
    nested = define_task(
        "nested", "Compose nested fields", task_action=echo,
        args_mapping=Request(Options(encoding.quote), record.labels),
        outputs_mapping=Request(Options(published.quote), []),
    )
    whole = define_task(
        "whole", "Reuse a nested record", task_action=echo,
        args_mapping=Request(options.quote, record.labels),
    )
    projected = define_task(
        "projected", "Select a field", task_action=echo,
        args_mapping=Request(
            Options(source.field("options", Options).field("encoding", str).quote),
            record.labels,
        ),
    )
    async with define_frame(preset={"source": record, "options": record.options}) as frame:
        context = WorkflowExecutionContext(
            False, date(2026, 9, 23), False, logging.getLogger("mapping-example"), frame,
        )
        await define_workflow("Direct", direct).execute(context)
        first = await define_workflow("Nested", nested).execute(context)
        second = await define_workflow("Whole", whole).execute(context)
        third = await define_workflow("Projected", projected).execute(context)
        assert await frame.get("target") is record
        assert first.task_outputs["nested"].options.encoding == "ascii"
        assert first.task_outputs["nested"].labels is record.labels
        assert await frame.get("published") == "ascii"
        assert not frame.has("labels")
        assert second.task_outputs["whole"].options is record.options
        assert third.task_outputs["projected"].options.encoding == "utf-16"


asyncio.run(main())
```

The direct quote preserves the whole record. The nested template builds a new
`Options` from the variable default while preserving the ordinary shared list.
Only the quoted encoding output is published; the literal list is unmapped.
The nested whole-record quote preserves the supplied `Options` instance. Finally,
the chained projection reads the original record without defining new variables.

Use separate top-level field quotes when a task reads independent variables;
put the same markers inside nested dataclass templates when grouping those
inputs. Use a nested whole-record quote when the group already has one owner.
Containers are leaves: markers hidden inside lists or dictionaries are not
recursively resolved. Put quotes in dataclass fields instead.

## Defaults, publication and ownership

Effective Frame/configuration values outrank variable defaults. Variable
factories are lazy and shared per execution. A missing field quote can finally
use the constructor field's default; an existing definition that fails never
falls back. Scope-to-record conversion retains constructor defaults. Use
factories for independent mutable defaults.

Whole-record mappings must exactly match the callable's dataclass annotation,
including generic arguments. Concrete records keep identity. Template records
are rebuilt without mutating the template; ordinary non-record literal values
keep their references. Cyclic templates are rejected, but acyclic shared
subtemplates may be reused.

Whole-record output publication is shallow. An existing target scope receives
direct fields atomically; otherwise it receives the record itself. Nested
dataclasses remain values, not recursively flattened bindings. Action outputs
target the shared workflow Frame; context outputs stay within the owning task
subtree. `task_outputs` retains the complete action record even when only a
subset is published.

Output names must be unique after normalization, projections remain input-only,
and failed validation publishes no partial set. Prefer explicit destinations
to mutation of input objects. See [variable types and boxes](workflow-types.md)
for opt-in conversion at individual quote boundaries.
