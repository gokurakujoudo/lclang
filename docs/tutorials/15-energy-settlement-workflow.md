# Case Study: Energy Settlement Workflow

## What you will learn

This chapter builds a complete command for a cold-storage operator. At the end
of each shift, the operator turns two electricity-meter readings into a billable
usage figure, applies the contracted tariff and tax, and writes a settlement
file for the finance team.

Imagine this is the hand-off between the facilities desk and accounting. The
facilities desk owns the readings, the commercial contract owns the rate, and
finance needs a repeatable report plus enough evidence to explain a failure the
next morning. That division of responsibility is why this is a workflow rather
than one large Python function.

The example combines the pieces from the configuration, CLI, logging, masking,
scoped-values, and tree-workflow chapters. It demonstrates how to:

- configure scoped meter, tariff, customer, path, and secret values in `.lclcfg`;
- pass intermediate results between ordered tasks with `TaskVar`;
- acquire the result file as a task-local context resource;
- write ordinary step logs followed by the final workflow status tree;
- retain exceptions and failed status in the same log file;
- run sunny, rainy, dry-run, verbose, and help commands; and
- prove that help exposes every external value but no intermediate value.

Everything runs inside `TemporaryDirectory`, so the configuration, reports, and
log disappear automatically after the example. A production application would
retain the workflow definition and point the configuration at durable paths.

## Start with the configuration contract

The settlement policy groups scoped names on consecutive rows and separates
functional sections with blank lines. Qualified leaves infer their prefixes,
so no `FRAME_PROXY` declarations are needed. The writer credential has a
trailing `!`, so lclang-owned diagnostics mask its definition, value, and
failures without changing the runtime name.

<!-- lclang-doc-exec -->
```python
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.config import load_config


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-energy-config-") as directory:
        root = Path(directory)
        config_path = root / "settlement.lclcfg"
        config_path.write_text(
            "# scope: report paths\n"
            f"paths.output_dir: {json.dumps(str(root / 'results'))} # Output directory\n"
            'paths.output_name: "settlement.txt" # Output filename\n'
            "\n"
            "# scope: meter readings\n"
            "meter.start: 1000.0 # Opening cumulative kWh\n"
            "meter.end: 1250.0 # Closing cumulative kWh\n"
            "\n"
            "# scope: tariff policy\n"
            "tariff.unit_rate: 0.18 # USD per kWh\n"
            "tariff.tax_rate: 0.08 # Tax decimal\n"
            "\n"
            "# Customer and credential\n"
            'customer.name: "North Harbor Cold Storage" # Report customer\n'
            'secrets.account_token!: "warehouse-writer-token" # Writer token\n'
            "\n"
            "# CLI logging and lunch\n"
            f"logger.file.app.directory: {json.dumps(str(root))} # Formal log directory\n"
            'logger.file.app.filename: "settlement.log" # Formal log filename\n'
            'logger.file.app.level: "INFO" # Application threshold\n'
            'lunch.options: ["noodles"] # Successful-run lunch choice\n',
            encoding="utf-8",
        )

        config = await load_config(config_path)
        frame = config.frame_factory().create()
        try:
            assert await frame.get("paths.output_name") == "settlement.txt"
            assert await frame.get("tariff.unit_rate") == 0.18
            assert await frame.get("customer.name") == "North Harbor Cold Storage"
            assert frame.is_masked("secrets.account_token") is True
            assert config.masked_names == frozenset({"secrets.account_token"})
        finally:
            await frame.close()


asyncio.run(main())
```

The scoped names are still exact names. `tariff.unit_rate` does not use relative
lookup, and a CLI override must use that complete spelling. The log settings are
scoped beneath `logger` and consumed by the CLI framework before it creates the
invocation logger.

## Build the complete settlement command

The full program below has four business tasks:

1. validate the readings and calculate usage;
2. calculate the energy subtotal;
3. calculate tax and the final total; and
4. render the finance report.

The first three tasks explicitly publish their outputs to the shared execution
Frame. The next sibling reads those values through its own derived task Frame.
The report stream is different: it belongs only to the final task, so an async
context task opens it, mixes it into that task Frame, and closes it afterward.

Notice the keyword form used for every dataclass value, such as
`ReadingArgs(start=meter_start.quote, end=meter_end.quote)`. A reader can see
which workflow variable feeds which Python field without remembering field
order. The same form is used when actions return outputs.

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TextIO

import lclang.workflow as wf
from lclang.cli import CliEntrance, CommandGroup


@dataclass
class ReadingArgs:
    start: float
    end: float


@dataclass
class UsageArgs:
    usage: float
    unit_rate: float


@dataclass
class TaxArgs:
    subtotal: float
    tax_rate: float


@dataclass
class FileArgs:
    output_dir: str
    output_name: str


@dataclass
class ReportArgs:
    customer_name: str
    usage: float
    subtotal: float
    tax: float
    total: float
    account_token: str
    stream: TextIO
    output_dir: str
    output_name: str


@dataclass
class NumberOutput:
    value: float


@dataclass
class TaxOutput:
    tax: float
    total: float


@dataclass
class FileOutput:
    stream: TextIO


@dataclass
class ReportOutput:
    path: str


meter_start = wf.define_variable[float](
    "meter.start", "Opening cumulative meter reading in kWh"
)
meter_end = wf.define_variable[float](
    "meter.end", "Closing cumulative meter reading in kWh"
)
unit_rate = wf.define_variable[float](
    "tariff.unit_rate", "Contract energy price in USD per kWh"
)
tax_rate = wf.define_variable[float](
    "tariff.tax_rate", "Settlement tax rate as a decimal"
)
customer_name = wf.define_variable[str](
    "customer.name", "Customer name printed on the settlement"
)
output_dir = wf.define_variable[str](
    "paths.output_dir", "Directory that receives the settlement file"
)
output_name = wf.define_variable[str](
    "paths.output_name", "Settlement output filename"
)
account_token = wf.define_variable[str](
    "secrets.account_token",
    "Writer credential required before report creation",
    is_masked=True,
)

# Intermediate variables are assigned before later tasks read them.
usage = wf.define_variable[float]("usage")
subtotal = wf.define_variable[float]("subtotal")
tax = wf.define_variable[float]("tax")
total = wf.define_variable[float]("total")
report_stream = wf.define_variable[TextIO]("report_stream")


async def calculate_usage(
    context: wf.TaskContext,
    args: ReadingArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> NumberOutput:
    with status_mgr.add_step("subtract_readings", "Validate and subtract readings"):
        if args.end <= args.start:
            raise ValueError(
                f"end reading {args.end} must exceed start reading {args.start}"
            )
        value = args.end - args.start
    context.logger.info("validated usage=%.2f kWh", value)
    return NumberOutput(value=value)


async def calculate_subtotal(
    context: wf.TaskContext,
    args: UsageArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> NumberOutput:
    with status_mgr.add_step("price_usage", "Multiply usage by contracted rate"):
        value = round(args.usage * args.unit_rate, 2)
    context.logger.info("calculated subtotal=%.2f USD", value)
    return NumberOutput(value=value)


async def calculate_tax(
    context: wf.TaskContext,
    args: TaxArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> TaxOutput:
    with status_mgr.add_step("apply_tax", "Apply settlement tax"):
        tax_value = round(args.subtotal * args.tax_rate, 2)
        total_value = round(args.subtotal + tax_value, 2)
    context.logger.info(
        "calculated tax=%.2f USD total=%.2f USD", tax_value, total_value
    )
    return TaxOutput(tax=tax_value, total=total_value)


@asynccontextmanager
async def open_report(
    context: wf.TaskContext,
    args: FileArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> AsyncIterator[FileOutput]:
    path = Path(args.output_dir) / args.output_name
    if context.is_dryrun:
        context.logger.info("DRY RUN would create settlement report %s", path)
        stream: TextIO = io.StringIO()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("w", encoding="utf-8")
        context.logger.info("opened settlement report %s", path)
    try:
        yield FileOutput(stream=stream)
    finally:
        stream.close()
        context.logger.info(
            "%s settlement report %s",
            "discarded dry-run" if context.is_dryrun else "closed",
            path,
        )


async def write_report(
    context: wf.TaskContext,
    args: ReportArgs,
    status_mgr: wf.ExecutionStatusManager,
) -> ReportOutput:
    with status_mgr.add_step("render_report", "Render the finance settlement"):
        if not args.account_token:
            raise ValueError("writer credential is empty")
        text = (
            "Warehouse energy settlement\n"
            f"Customer: {args.customer_name}\n"
            f"Usage: {args.usage:.2f} kWh\n"
            f"Subtotal: {args.subtotal:.2f} USD\n"
            f"Tax: {args.tax:.2f} USD\n"
            f"Total: {args.total:.2f} USD\n"
        )
        args.stream.write(text)
    path = str(Path(args.output_dir) / args.output_name)
    context.logger.info(
        "%s settlement report for %s",
        "DRY RUN rendered" if context.is_dryrun else "wrote",
        args.customer_name,
    )
    return ReportOutput(path=path)


usage_task = wf.define_task(
    "calculate_usage",
    "Calculate metered usage",
    task_action=calculate_usage,
    args_mapping=ReadingArgs(start=meter_start.quote, end=meter_end.quote),
    outputs_mapping=NumberOutput(value=usage.quote),
)
subtotal_task = wf.define_task(
    "calculate_subtotal",
    "Price energy usage",
    task_action=calculate_subtotal,
    args_mapping=UsageArgs(usage=usage.quote, unit_rate=unit_rate.quote),
    outputs_mapping=NumberOutput(value=subtotal.quote),
)
tax_task = wf.define_task(
    "calculate_tax",
    "Apply settlement tax",
    task_action=calculate_tax,
    args_mapping=TaxArgs(subtotal=subtotal.quote, tax_rate=tax_rate.quote),
    outputs_mapping=TaxOutput(tax=tax.quote, total=total.quote),
)
file_context = wf.define_context_task(
    "open_report",
    "Own the settlement output file",
    open_report,
    FileArgs(output_dir=output_dir.quote, output_name=output_name.quote),
    FileOutput(stream=report_stream.quote),
)
report_task = wf.define_task(
    "write_report",
    "Write finance settlement",
    task_action=write_report,
    args_mapping=ReportArgs(
        customer_name=customer_name.quote,
        usage=usage.quote,
        subtotal=subtotal.quote,
        tax=tax.quote,
        total=total.quote,
        account_token=account_token.quote,
        stream=report_stream.quote,
        output_dir=output_dir.quote,
        output_name=output_name.quote,
    ),
    context_tasks=[file_context],
)
root_task = wf.define_task(
    "settlement",
    "Settle one meter period",
    children=[usage_task, subtotal_task, tax_task, report_task],
)
workflow = wf.define_workflow("Energy settlement workflow", root_task)
command = workflow.to_cli("settle", "Create one audited energy settlement")
application = CliEntrance(
    command_group=CommandGroup(
        name="root",
        description="Cold-storage settlement tools",
        commands=[command],
    ),
    version="1.0.0",
)


def config_source(root: Path) -> str:
    return (
        "# scope: report paths\n"
        f"paths.output_dir: {json.dumps(str(root / 'results'))} # Output directory\n"
        'paths.output_name: "settlement.txt" # Output filename\n'
        "\n"
        "# scope: meter readings\n"
        "meter.start: 1000.0 # Opening cumulative kWh\n"
        "meter.end: 1250.0 # Closing cumulative kWh\n"
        "\n"
        "# scope: tariff policy\n"
        "tariff.unit_rate: 0.18 # USD per kWh\n"
        "tariff.tax_rate: 0.08 # Tax decimal\n"
        "\n"
        "# Customer and credential\n"
        'customer.name: "North Harbor Cold Storage" # Report customer\n'
        'secrets.account_token!: "warehouse-writer-token" # Writer token\n'
        "\n"
        "# CLI logging and lunch\n"
        f"logger.file.app.directory: {json.dumps(str(root))} # Formal log directory\n"
        'logger.file.app.filename: "settlement.log" # Formal log filename\n'
        'logger.file.app.level: "INFO" # Application threshold\n'
        'lunch.options: ["noodles"] # Successful-run lunch choice\n'
    )


async def invoke(config_path: Path, *options: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = await application.run(
            [
                "python",
                "settlement.py",
                "settle",
                "--config",
                str(config_path),
                *options,
            ]
        )
    return status, stdout.getvalue(), stderr.getvalue()


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-energy-workflow-") as directory:
        root = Path(directory)
        config_path = root / "settlement.lclcfg"
        config_path.write_text(config_source(root), encoding="utf-8")
        result_dir = root / "results"

        # Help lists the eight external variables and hides five intermediates.
        help_stdout = io.StringIO()
        with redirect_stdout(help_stdout):
            help_status = await application.run(
                ["python", "settlement.py", "settle", "--help"]
            )
        help_text = help_stdout.getvalue()
        assert help_status == 0
        assert "Usage: settlement.py settle [options]" in help_text
        assert "meter.start" in help_text and "secrets.account_token" in help_text
        assert "logger.file.<sink>" in help_text
        assert "logger.file.default" in help_text

        # Sunny: config supplies most inputs; one scoped CLI override changes price.
        sunny_status, sunny_stdout, sunny_stderr = await invoke(
            config_path,
            "--override",
            "tariff.unit_rate",
            "LCL[0.20]",
        )
        assert (sunny_status, sunny_stdout) == (0, "")
        assert "validated usage=250.00 kWh" in sunny_stderr
        assert "[SUCCESS] Energy settlement workflow" in sunny_stderr
        result_path = result_dir / "settlement.txt"
        assert result_path.read_text(encoding="utf-8") == (
            "Warehouse energy settlement\n"
            "Customer: North Harbor Cold Storage\n"
            "Usage: 250.00 kWh\n"
            "Subtotal: 50.00 USD\n"
            "Tax: 4.00 USD\n"
            "Total: 54.00 USD\n"
        )
        sunny_log = sorted(root.glob("settlement.*.log"))[-1].read_text(encoding="utf-8")
        assert "validated usage=250.00 kWh" in sunny_log
        assert "calculated subtotal=50.00 USD" in sunny_log
        assert "calculated tax=4.00 USD total=54.00 USD" in sunny_log
        assert "[SUCCESS] Energy settlement workflow" in sunny_log
        assert "lunch option: noodles" in sunny_stderr
        assert "lunch option: noodles" in sunny_log

        # Rainy: an invalid scoped override fails the first task and logs the error.
        rainy_status, rainy_stdout, rainy_stderr = await invoke(
            config_path,
            "--override",
            "meter.end",
            "LCL[900.0]",
            "--override",
            "paths.output_name",
            "rainy.txt",
        )
        assert rainy_status == 2
        assert "[SKIPPED] calculate_subtotal" in rainy_stderr
        assert "task error: [settlement.calculate_usage] ERROR" in rainy_stderr
        assert "ValueError: end reading 900.0" in rainy_stderr
        assert "[ERROR] Energy settlement workflow" in rainy_stderr
        assert "lunch option: no lunch!" in rainy_stderr
        assert not (result_dir / "rainy.txt").exists()
        rainy_log = sorted(root.glob("settlement.*.log"))[-1].read_text(encoding="utf-8")
        assert "end reading 900.0 must exceed start reading 1000.0" in rainy_log
        assert "task error: [settlement.calculate_usage] ERROR" in rainy_log
        assert "task complete: [settlement.calculate_usage] ERROR" in rainy_log
        assert "[ERROR] Energy settlement workflow" in rainy_log
        assert "[SKIPPED] calculate_subtotal" in rainy_log
        assert "lunch option: no lunch!" in rainy_log

        # Dry-run follows every calculation but substitutes an in-memory file.
        dry_status, dry_stdout, dry_stderr = await invoke(
            config_path,
            "--override",
            "paths.output_name",
            "preview.txt",
            "--dryrun",
        )
        assert (dry_status, dry_stdout) == (0, "")
        assert "DRY RUN would create settlement report" in dry_stderr
        assert "DRY RUN rendered settlement report" in dry_stderr
        assert not (result_dir / "preview.txt").exists()
        dry_log = sorted(root.glob("settlement.*.log"))[-1].read_text(encoding="utf-8")
        assert "DRY RUN would create settlement report" in dry_log
        assert "DRY RUN rendered settlement report" in dry_log
        assert "discarded dry-run settlement report" in dry_log

        # Verbose adds parser/evaluation traces to stderr and the same log file.
        verbose_status, verbose_stdout, verbose_stderr = await invoke(
            config_path,
            "--verbose",
            "--override",
            "paths.output_name",
            "verbose.txt",
        )
        assert verbose_status == 0
        assert "validated usage=250.00 kWh" in verbose_stderr
        assert (result_dir / "verbose.txt").is_file()
        assert "[lclang.parse]" not in verbose_stderr
        assert "[lclang.evaluate]" in verbose_stderr
        assert "*masked*" in verbose_stderr
        assert "warehouse-writer-token" not in verbose_stderr
        verbose_lines = [line.rsplit(" | ", 1)[-1] for line in verbose_stderr.splitlines()]
        exact_verbose_messages = (
            "[lclang.evaluate] definition='meter.start' expression=(LclConstant) 1000.0 result=(float) 1000.0",
            "[lclang.evaluate] definition='meter.end' expression=(LclConstant) 1250.0 result=(float) 1250.0",
            "[lclang.lookup] name='usage' owner='cli_runtime' source=external-provided value=(float) 250.0",
            "[lclang.evaluate] definition='tariff.unit_rate' expression=(LclConstant) 0.18 result=(float) 0.18",
            "[lclang.lookup] name='subtotal' owner='cli_runtime' source=external-provided value=(float) 45.0",
            "[lclang.evaluate] definition='tariff.tax_rate' expression=(LclConstant) 0.08 result=(float) 0.08",
            "[lclang.evaluate] definition='secrets.account_token' expression=*masked* result=*masked*",
        )
        positions = [verbose_lines.index(message) for message in exact_verbose_messages]
        assert positions == sorted(positions)
        final_log = sorted(root.glob("settlement.*.log"))[-1].read_text(encoding="utf-8")
        assert "[lclang.parse]" not in final_log
        assert "*masked*" in final_log
        assert "warehouse-writer-token" not in final_log


asyncio.run(main())
```

The `invoke` helper passes exact argument tokens to `CliEntrance`, which is the
same behavior a real shell process reaches after argument adaptation. The
equivalent operator commands are:

```console
python settlement.py settle --help
python settlement.py settle --config settlement.lclcfg --override tariff.unit_rate "LCL[0.20]"
python settlement.py settle --config settlement.lclcfg --override meter.end "LCL[900.0]"
python settlement.py settle --config settlement.lclcfg --override paths.output_name preview.txt --dryrun
python settlement.py settle --config settlement.lclcfg --verbose
```

## Read the sunny log

The default log format adds timestamps and source locations, so those prefixes
vary. The meaningful message sequence contains lines like:

```text
validated usage=250.00 kWh
task complete: [settlement.calculate_usage] SUCCESS
calculated subtotal=50.00 USD
calculated tax=4.00 USD total=54.00 USD
opened settlement report .../results/settlement.txt
wrote settlement report for North Harbor Cold Storage
closed settlement report .../results/settlement.txt
workflow complete: [settle] SUCCESS:
[SUCCESS] Energy settlement workflow
└─ [SUCCESS] settlement: Settle one meter period
lunch option: noodles
```

Ordinary `INFO` application logs appear on stderr and in the configured file
before the final tree. Each task's
`add_step(...)` scope also appears under that task, which makes the final tree a
useful audit outline without forcing every calculation into the log message
format.

## Read the rainy log

The rainy override makes the closing reading lower than the opening reading.
The first task raises `ValueError`; the CLI process still closes its Frames and
logger, returns exit status `2`, prints the error records to stderr, and appends
the same evidence to the configured file:

```text
task error: [settlement.calculate_usage] ERROR
Traceback (most recent call last):
...
ValueError: end reading 900.0 must exceed start reading 1000.0
task complete: [settlement.calculate_usage] ERROR
workflow complete: [settle] ERROR:
[ERROR] Energy settlement workflow: ...
   └─ [ERROR] settlement: ...
      ├─ [ERROR] calculate_usage: ...
      ├─ [SKIPPED] calculate_subtotal: Price energy usage
      ├─ [SKIPPED] calculate_tax: Apply settlement tax
      └─ [SKIPPED] write_report: Write finance settlement
lunch option: no lunch!
```

No rainy result file is created because execution stops before the file context
is entered. This is the practical value of acquiring the file only around the
task that needs it.

## Understand the CLI log

The entry point resolves `logger.console` and the named `logger.file` sinks
through the final Frame, then opens one process scope. `logger.file.default`
only supplies absent fields; explicit sink settings always win. Command-line
`-o` overrides use the same qualified keys as the configuration file.

Each invocation creates a new permanent file segment. Its first line identifies
that file. The writer records the execution banner, redacted argv, and lazy
winning configuration without a fixed four-record position. Rotation, when
enabled, closes a segment with the permanent path of its successor. Old
segments are never appended to or renamed.

The sunny, rainy, dry-run, and verbose invocations above therefore have separate
segments. Inspecting the newest segment selects the corresponding invocation.
All application logging goes to stderr and the configured files; command-result
stdout remains available for machine-readable results.

## Understand dry-run and verbose behavior

Dry-run changes the workflow's resource action, not logging ownership. Every
task runs its calculation and closes its context, while the report remains in
memory. Its diagnostic records still use the same background writer.

`--verbose` lowers the global and enabled output thresholds to DEBUG. It never
enables a disabled sink or removes a source filter. Runtime evaluation and
lookup records retain bounded, masked value rendering. Preparation before the
scope starts is not replayed. Every Frame closes before the log queue drains,
so normal cleanup diagnostics remain in the invocation segment.

## Why help is part of the contract

Help shows external workflow inputs plus the shared logger configuration
syntax. Logging keys do not become TaskVars and are not rejected as unknown
workflow business overrides. Rendering help does not load configuration,
evaluate Frames, or open log files.

[Previous: Tree workflows](14-tree-workflows.md) | [Next: Python utilities for downstream applications](16-python-utilities.md) | [Return to the series introduction](README.md)
