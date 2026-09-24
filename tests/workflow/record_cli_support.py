"""Static dataclass declarations shared by CLI record acceptance cases."""

from dataclasses import dataclass, field

from lclang.workflow import (
    ExecutionStatusManager,
    TaskContext,
    Workflow,
    define_task,
    define_workflow,
)


@dataclass
class Dialect:
    """Nested conversion defaults."""

    delimiter: str = field(default=",", metadata={"help": "Input separator"})
    quote: str = '"'


@dataclass
class CsvOptions:
    """Record containing literal, null, factory and non-init fields."""

    encoding: str = field(default="utf-8", metadata={"help": "Input encoding"})
    dialect: Dialect = field(default_factory=Dialect)
    headers: list[str] = field(default_factory=list[str])
    null: str | None = None
    computed: int = field(default=3, init=False)


async def echo_csv(
    context: TaskContext,
    args: CsvOptions,
    status_mgr: ExecutionStatusManager,
) -> CsvOptions:
    """Return materialized options for CLI and direct execution comparisons."""
    return args


def make_workflow(mapping: CsvOptions) -> Workflow:
    """Use one mapping through the real workflow executor."""
    return define_workflow(
        "CSV",
        define_task(
            "convert",
            "Convert",
            task_action=echo_csv,
            args_mapping=mapping,
        ),
    )
