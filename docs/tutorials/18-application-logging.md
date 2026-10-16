# Application logging

This chapter is for developers embedding lclang in a Python application. It
explains who owns logging, how to enable execution diagnostics for one operation,
and where to report failures so users receive one complete explanation.

`lclang.logger` also works without LCL evaluation. Its handler scope owns a queue
writer and output sinks; business code uses named loggers inside that scope.

The output blocks below are captured from the exact examples in isolated
processes. File examples print their event records after shutdown and omit the
segment header containing the generated path. Displayed fixture paths use the
filename alone. `<string>` identifies source supplied inline; saving the Python
program in a file gives its traceback that file's location. Evaluation/failure
identifiers and task names can differ in a longer-running application.

## Choose the integration at the application boundary

| Application | Recommended entry point |
| --- | --- |
| Standalone Python program | Own one `use_logger_handler(config)` scope and obtain named loggers with `await use_logger(...)`. |
| lclang CLI command | Use `context.logger`; CLI owns configuration, logging and the final failure report. |
| Workflow action | Use `context.logger` and `context.log_event(...)`; retain the workflow's task and cleanup reporting. |
| Application with an existing logging system | Borrow a `logging.Logger` through `use_verbose`; install `LclExceptionFormatter` on an application-owned handler when desired. |
| Reusable application library | Accept a logger or use an application-selected stdlib source name; leave handlers and uncaught-error hooks to the application. |

Keep handler installation in the process entry point. One process can have only
one active lclang handler scope, including across concurrent tasks and threads.
Start it after worker creation. All work that can log, including resource cleanup,
must finish before the scope closes. A service keeps the scope around its server
run; a finite program keeps it around that run's business operations.

CLI and workflow entry points already manage their logger lifecycle. A command,
route or task should not create another handler scope. See the
[service entry points](../reference/logger.md#service-entry-points) for server and
worker examples, and the [CLI tutorial](09-command-line-applications.md) for command
ownership.

## Own the writer once and pass named loggers to business code

Use stable source names such as `example.billing`. Put a request identifier in
the message, a logger prefix or application record metadata; avoid creating a new
logger name for every request. Stdlib loggers and their names persist in the
process registry.

This example runs two operations concurrently under one writer. The temporary
directory isolates its file output and closes after the writer has drained.

<!-- lclang-doc-case: application-log-records -->

<!-- lclang-doc-exec -->
```python
import asyncio
from tempfile import TemporaryDirectory

from lclang.logger import Logger, LoggerHandlerConfig, use_logger, use_logger_handler


async def process_order(logger: Logger, quantity: int) -> int:
    total = quantity * 6
    logger.info("Processed order: quantity=%d total=%d", quantity, total)
    return total


async def main() -> None:
    with TemporaryDirectory() as directory:
        config = LoggerHandlerConfig(
            timezone="utc",
            format="%(levelname)s | %(name)s | %(message)s",
            console={"enabled": False},
            file={"application": {"directory": directory, "level": "INFO"}},
        )
        async with use_logger_handler(config) as runtime:
            first = await use_logger("example.billing", prefix="[order=A]")
            second = await use_logger("example.billing", prefix="[order=B]")
            totals = await asyncio.gather(
                process_order(first, 2), process_order(second, 3)
            )
            assert totals == [12, 18]
        path = runtime.metrics.sinks["file.application"].path
        assert path is not None
        text = path.read_text(encoding="utf-8")
        assert "[order=A] Processed order: quantity=2 total=12" in text
        assert "[order=B] Processed order: quantity=3 total=18" in text
        assert runtime.metrics.records_written == 2
        print("\n".join(text.splitlines()[1:]))


asyncio.run(main())
```

The program prints the file's event records after shutdown. The segment header
contains its generated path and is not included in this display:

<!-- lclang-doc-output: stdout -->
```text
INFO | example.billing | [order=A] Processed order: quantity=2 total=12
INFO | example.billing | [order=B] Processed order: quantity=3 total=18
```
<!-- /lclang-doc-case -->

`process_order` receives a logger and owns no handler. Both operations use the
same source name with different prefixes. `gather` finishes both producers
before scope exit drains the queue. Read files and final metrics after that
exit; an enqueued record may not have been written yet.

Use logging templates and arguments, as above, to defer message formatting.
Queue records are shallow snapshots, so finish constructing arguments before
logging and do not mutate referenced objects afterwards. For expensive business
summaries, check `logger.isEnabledFor(logging.DEBUG)` before constructing them.
That checks producer admission; a sink can still reject the resulting record.

## Use compact records for task boundaries

Pass `compact=True` to a downstream logger method when a task boundary needs
only the message and the shared timestamp, level and thread/process prefix.
Ordinary calls on the same logger keep the full default layout.

<!-- lclang-doc-exec -->
```python
import asyncio
import io

from lclang.logger import Logger, use_logger, use_logger_handler


async def main() -> None:
    output = io.StringIO()
    async with use_logger_handler({"console": {"stream": output}}):
        logger: Logger = await use_logger("catalog.batch")
        logger.info("Task started", compact=True)
        logger.warning("Copied %d rows", 3)
        logger.info("Task finished", compact=True)
    lines = output.getvalue().splitlines()
    assert [line.split(" | ")[-1] for line in lines] == [
        "Task started", "Copied 3 rows", "Task finished"
    ]
    assert len(lines[0].split(" | ")) == len(lines[2].split(" | ")) == 4
    assert " | catalog.batch | " in lines[1]
    assert ".py:" in lines[1] and " | WARN  | " in lines[1]


asyncio.run(main())
```

The first and last lines omit the logger name and caller location. The warning
between them retains both, and formats its argument in the writer. The scope
drains all three records before the assertions run. `compact=False` is the
default on `log`, `debug`, `info`, `warning`, `error`, `critical` and `exception`.
The flag changes the default layout for one record; an explicitly configured
`format` still controls its selected fields. Exception records keep their full
diagnostic tree in either layout.

## Configure levels and outputs before starting business work

`LoggerHandlerConfig` accepts Python declarations or mappings. If the application
loads `.lclcfg`, first call `await resolve_logger_config(frame, verbose=verbose)`
on its configuration Frame, then enter the handler scope with the result. See
[configuration without CLI](../reference/logger.md#configuration-without-cli)
for a complete file-backed example. The resolver does not open a handler scope
or close the supplied Frame.

Choose console and file thresholds separately. A useful application policy is
INFO on stderr and DEBUG in a diagnostic file. Set the producer/global threshold
to DEBUG when collecting verbose records, and enable DEBUG in the intended sink.
An explicitly configured named logger can also reject records before they reach
the root handler. List loggers in `takeover_loggers` only when the application
intends to replace their handlers and levels for the scope; other named loggers
retain their stdlib settings.

`use_verbose` emits DEBUG records but does not lower thresholds. The framework
formatter displays their level as `TRACE` without changing the original record.
`resolve_logger_config(..., verbose=True)` lowers the global and enabled sink
thresholds to DEBUG. Disabled sinks stay disabled, and source filters remain in
effect. `logger_names` on a file sink selects a source and its dot-separated
descendants; it does not set the producer's level.

Keep console output on stderr when stdout carries a result or another program's
input. The default format uses a five-character level column,
`thread_name(pid)` and `qualified_module_name.py:lineno:func_name`; verbose
and workflow lifecycle records omit the source column. All lclang formatters
display WARNING as WARN, CRITICAL as CRIT, NOTSET as UNSET and marked verbose
records as TRACE. Configuration names and numeric severities stay unchanged.
Use this default or choose an explicit application format. Explicit
formats are respected. `timezone="utc"` changes displayed timestamps to UTC;
the default uses local time with a numeric offset. It has no effect when the
chosen format omits `%(asctime)s`.

Named files use permanent segment paths. Use `runtime.metrics.sinks` to find
those paths; the configured filename is the base name, not a promise that the
writer will create exactly that path. Rotation creates new segments and retains
old ones. The application or its deployment tooling owns retention.

## Trace one operation and report its final failure once

Let business functions propagate failures with their existing diagnostics. The
application boundary decides whether to recover, return an error response or
terminate. Log one complete exception there, after owned resources have closed.
If execution and cleanup both fail, the resulting LCL group retains both
members. Logging before cleanup can miss the final failure set.

This boundary handles a failed calculation and records it once. The Boolean
`verbose` argument enables the same business code to run with or without tracing.

<!-- lclang-doc-case: final-calculation-report -->

<!-- lclang-doc-exec -->
```python
import asyncio
from tempfile import TemporaryDirectory

from lclang.error import LclError
from lclang.lang import define_frame, define_module
from lclang.logger import Logger, LoggerHandlerConfig, use_logger, use_logger_handler, use_verbose


PRICING = define_module("pricing", {
    "total": "amount / divisor",
    "RESULT": "total + 1",
})


async def calculate(logger: Logger, *, verbose: bool) -> object:
    with use_verbose(logger, enabled=verbose):
        async with define_frame(PRICING, preset={"amount": 39, "divisor": 0}) as frame:
            return await frame.get("RESULT")


async def main() -> None:
    with TemporaryDirectory() as directory:
        config = LoggerHandlerConfig(
            level="DEBUG",
            format="%(levelname)s | %(message)s",
            traceback_style="compact",
            console={"enabled": False},
            file={"diagnostic": {"directory": directory, "level": "DEBUG"}},
        )
        async with use_logger_handler(config) as runtime:
            logger = await use_logger("example.billing")
            try:
                await calculate(logger, verbose=True)
            except LclError as error:
                identity = error.verbose_failure_id
                assert identity is not None
                logger.exception("Order calculation failed")
            else:
                raise AssertionError("The zero divisor must fail")
        path = runtime.metrics.sinks["file.diagnostic"].path
        assert path is not None
        text = path.read_text(encoding="utf-8")
        assert "TRACE | Failed while evaluating total" in text
        assert "Cached failures: total, RESULT" in text
        assert f"(failure {identity})" in text
        assert text.count("Error in evaluating RESULT") == 1
        assert "[LCL131421: division by zero]" in text
        assert "Python traceback:" in text
        print("\n".join(text.splitlines()[1:]))


asyncio.run(main())
```

The program prints the diagnostic file's event records, including one complete
exception report:

<!-- lclang-doc-output: stdout -->
```text
TRACE | Read amount from external input in Frame "LCL_IMPORTS": (int) 39 (evaluation E2)
TRACE | Read divisor from external input in Frame "LCL_IMPORTS": (int) 0 (evaluation E2)
TRACE | Failed while evaluating total [LCL131421: division by zero] (failure F3)
  Type: LclEvaluationError
  Source: "<string>":1:1
  Evaluation: E2
  Request: RESULT -> total
  Frames: requested from "pricing"; defined in "pricing"
  Lookup path: pricing
  Execution: new evaluation
  Task: Task-3
  Phase: arithmetic operation
TRACE | Could not evaluate RESULT (failure F3)
  Cached failures: total, RESULT
ERROR | Order calculation failed
Error in evaluating RESULT [LCL131421: division by zero] (failure F3)
├─ Cause
│  └─ ZeroDivisionError: division by zero
└─ RESULT: total + 1 ("<string>":1:1)
   └─ total: amount / divisor ("<string>":1:1)
      ├─ amount: (int) 39 (external)
      ├─ divisor: (int) 0 (external)
      └─ Source: "<string>":1:1
         amount / divisor
         ^^^^^^^^^^^^^^^^
Python traceback:
LclEvaluationError [LCL131421: division by zero] (failure F3)
├─ Direct cause
│  └─ ZeroDivisionError: division by zero
└─ Traceback (most recent call last)
   ├─ File "<string>", line 33, in main
   │      await calculate(logger, verbose=True)
   └─ File "<string>", line 18, in calculate
          return await frame.get("RESULT")
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
```
<!-- /lclang-doc-case -->

`calculate` closes its Frame before `main` records the exception. The first
verbose failure explains the arithmetic stage and request context; propagation
and committed caches form a short root summary. `logger.exception` adds the
complete dependency tree, retained values, cause and Python stack. Their shared
failure identifier survives exit from `use_verbose`. Treat it as a process-local
reading aid; include your own request identifier for correlation across workers
or restarts.

Use `logger.exception` inside an active `except` block. For a retained exception
reported later, pass `exc_info=(type(error), error, error.__traceback__)` explicitly.
Formatting `str(error)` into the message and also supplying `exc_info` would
repeat the full diagnostic. A layer that logs and rethrows needs a clear agreement
with its caller about which boundary owns the final report.

When using CLI or workflow, let their existing failure boundaries report the
final error. Add application facts through ordinary events; logging the same
exception inside every command, action and wrapper produces repeated reports.
Preserve native cancellation, exit and interruption. Catch `LclError` or the
specific recoverable type, and retain unhandled members when processing groups;
see [exceptions and grouped failures](../reference/exceptions.md).

`use_verbose` is a synchronous context manager that spans `await`. Nested
`enabled=False` or `use_verbose(None)` suppresses an outer verbose scope; exit
restores it. Child tasks inherit the context at creation, so await them before
their borrowed logger's handler scope closes. Disable the scope or reject DEBUG
at the producer when tracing is unnecessary: both skip verbose-only rendering.
Handler filters act on records after their messages have been constructed.

## Keep an existing application logging system

An application can use LCL tracing and exception rendering without a lclang
handler scope. It continues to own its stdlib logger, handlers, levels and filters.
`LclExceptionFormatter` supplies the shared diagnostic tree and compact/full
Python stack policy on a handler the application selects.

This example filters verbose records at the handler while keeping an application
event. Removing that filter admits execution diagnostics. Disabling `use_verbose`
also keeps the business event, and avoids constructing trace-only messages.

<!-- lclang-doc-case: external-verbose-filter -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging

from lclang.lang import define_frame, define_module
from lclang.logger import LclExceptionFormatter, use_verbose


class BusinessOnly(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not bool(getattr(record, "lclang_verbose", False))


async def calculate(logger: logging.Logger, *, verbose: bool) -> None:
    module = define_module("pricing", {"RESULT": "amount * 2"})
    with use_verbose(logger, enabled=verbose):
        async with define_frame(module, preset={"amount": 3}) as frame:
            result = await frame.get("RESULT")
    assert result == 6
    logger.info("Calculated total=%d", result)


async def main() -> None:
    output = io.StringIO()
    logger = logging.Logger("example.existing", logging.DEBUG)
    handler = logging.StreamHandler(output)
    handler.setFormatter(LclExceptionFormatter(
        "%(levelname)s | %(message)s", traceback_style="compact"
    ))
    selected = BusinessOnly()
    handler.addFilter(selected)
    logger.addHandler(handler)
    try:
        await calculate(logger, verbose=True)
        assert output.getvalue() == "INFO | Calculated total=6\n"
        print("With the handler filter:")
        print(output.getvalue(), end="")
        handler.removeFilter(selected)
        output.seek(0)
        output.truncate(0)
        await calculate(logger, verbose=True)
        assert "TRACE | Evaluated RESULT" in output.getvalue()
        assert "RESULT: amount * 2 (" in output.getvalue()
        print("With verbose enabled:")
        print(output.getvalue(), end="")
        output.seek(0)
        output.truncate(0)
        await calculate(logger, verbose=False)
        assert output.getvalue() == "INFO | Calculated total=6\n"
        print("With verbose disabled:")
        print(output.getvalue(), end="")
    finally:
        logger.removeHandler(handler)
        handler.close()


asyncio.run(main())
```

The captured output shows that filtering and disabling verbose both retain the
business message:

<!-- lclang-doc-output: stdout -->
```text
With the handler filter:
INFO | Calculated total=6
With verbose enabled:
TRACE | Read amount from external input in Frame "LCL_IMPORTS": (int) 3 (evaluation E2)
TRACE | Evaluated RESULT: (int) 6 (evaluation E2)
TRACE | Evaluation tree for RESULT (evaluation E2)
  Result: (int) 6
RESULT: amount * 2 ("<string>":1:1)
└─ amount: (int) 3 (external)
INFO | Calculated total=6
With verbose disabled:
INFO | Calculated total=6
```
<!-- /lclang-doc-case -->

`use_verbose` borrows the logger and restores only its tracing context. The
application installs and removes this example's handler. In a real application,
keep an existing handler for its normal lifetime. Preserve one delivery route
per intended sink: a logger with its own handler and propagation to a parent
handler can deliver the same record twice.

Filters can select `lclang_verbose`, `lclang_stage`, `lclang_evaluation_id`,
`lclang_failure_id`, `lclang_context` and `lclang_tree`. Evaluation/failure IDs
can be `None`. These fields contain detached diagnostics; external formatters
should not request more Frame values or reload configuration while formatting.
Changing `traceback_style` to `"full"` restores all Python frames. Compact keeps
application and external-library frames, including a Python callback that calls
LCL again. Both styles retain exception chains and groups and leave the original
exception untouched. See [text diagnostics](../reference/text-display.md).

## Choose a policy for uncaught failures

Applications that let LCL failures escape to Python can explicitly call
`install_exception_hooks` at startup. It reports the LCL tree to stderr, followed
by the Python exception tree. It does not create a file logger. By default it
also handles worker-thread failures; `include_threads=False` leaves worker-thread
hooks unchanged. Pass `loop=your_loop` to cover that particular asyncio loop's
unhandled task failures, installing and restoring on its owning thread.

Save the following program as `application.py`. Run `python application.py` for
a normal result or `python application.py 0` for an uncaught division failure.
The program restores the previous hook after a normal return. If the calculation
raises, Python reaches the installed hook before restoration.

<!-- lclang-doc-case: uncaught-application-report -->

<!-- lclang-doc-file: application.py -->
```python
import asyncio
import sys

from lclang.lang import define_frame, define_module
from lclang.logger import install_exception_hooks


async def business(divisor: int) -> object:
    async def callback(amount: int) -> object:
        module = define_module("inner", {"value": "amount / divisor"})
        async with define_frame(module, preset={"amount": amount, "divisor": divisor}) as inner:
            return await inner.get("value")

    module = define_module("outer", {"RESULT": "callback(39)"})
    async with define_frame(module, preset={"callback": callback}) as outer:
        return await outer.get("RESULT")


async def main() -> None:
    divisor = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    result = await business(divisor)
    assert result == 13
    print(f"Result: {result}")


previous = sys.excepthook
installation = install_exception_hooks(traceback_style="compact", include_threads=False)
asyncio.run(main())
installation.restore()
assert sys.excepthook is previous
```

This launcher runs both commands and prints their captured output. For the
failed command it prints the LCL diagnostic at the beginning of stderr; the
complete stderr also contains the Python traceback. Its assertions check the
application frames and compact filtering without publishing installation paths.

<!-- lclang-doc-exec -->
```python
import os
import subprocess
import sys


environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
success = subprocess.run(
    [sys.executable, "application.py"], env=environment,
    capture_output=True, encoding="utf-8", check=True,
)
assert success.stdout == "Result: 13.0\n" and success.stderr == ""
print(success.stdout, end="")
failure = subprocess.run(
    [sys.executable, "application.py", "0"], env=environment,
    capture_output=True, encoding="utf-8", check=False,
)
assert failure.returncode == 1 and failure.stdout == ""
assert "in business" in failure.stderr and "in callback" in failure.stderr
frames = [line for line in failure.stderr.splitlines() if 'File "' in line]
assert not any("/src/lclang/" in line.replace("\\", "/") for line in frames)
diagnostic, separator, traceback = failure.stderr.partition("\nPython traceback:\n")
assert separator and traceback
print("Uncaught stderr diagnostic:")
print(diagnostic)
```

The normal result and the failed run's stderr diagnostic are:

<!-- lclang-doc-output: stdout -->
```text
Result: 13.0
Uncaught stderr diagnostic:
Error in evaluating RESULT [LCL131421: division by zero]
├─ Cause
│  └─ ZeroDivisionError: division by zero
└─ RESULT: callback(39) ("<string>":1:1)
   └─ callback: Python function business.<locals>.callback ("application.py":9)
      ├─ arg[0]: (int) 39 (argument)
      └─ value: amount / divisor ("<string>":1:1)
         ├─ amount: (int) 39 (external)
         ├─ divisor: (int) 0 (external)
         └─ Source: "<string>":1:1
            amount / divisor
            ^^^^^^^^^^^^^^^^
```
<!-- /lclang-doc-case -->

The failed run includes the Python callback's definition location and the LCL
requests nested inside it. Compact mode retains application frames around both
LCL calls; full mode restores the intervening lclang Python frames. No failure ID
appears here because verbose is disabled. Hooks do not manufacture a verbose
execution history.

Keep hooks active until the actual uncaught-report boundary. Restoring them in
a `finally` around `asyncio.run` disables their report before Python invokes
`sys.excepthook`. `restore()` is idempotent and preserves later third-party hook
replacements. Pure native exceptions and control signals delegate to the prior
handlers. A host with its own exception reporting can keep that policy and use
the formatter on its logging boundary instead.

Choose one stderr failure owner. If you log a failure to stderr and then leave it
uncaught with hooks installed, those two boundaries each produce a report. A
program that needs a file record plus the uncaught stderr report can use an
application-owned file handler for the caught record, then rethrow to the hook.
CLI already reports failures after cleanup and does not install exception hooks.

## Protect values and finish shutdown

LCL diagnostics retain existing binding masks and use bounded, protected value
summaries. Application messages have their own disclosure policy: passing a raw
token to `logger.info("token=%s", token)` exposes it. Log selected business fields,
omit secrets, or use the masking-aware business event helpers covered in
[Python utilities](16-python-utilities.md). Avoid copying an entire configuration
or request object into a log record.

Await producers and close business resources before leaving the handler scope.
Normal, failed and cancelled exits drain, flush and join the writer before
restoring logging state. Do not use a borrowed `Logger` afterwards. Startup can
fail when an enabled sink cannot initialize; handle that at the application's
startup boundary, where the logging runtime is not yet usable.

After shutdown, inspect `runtime.metrics.writer_errors` and per-sink metrics when
delivery matters. `records_written` counts a record once if any sink wrote it;
it is not a guarantee that every configured sink succeeded or that bytes reached
durable storage. Runtime sink failures are isolated and reported to
`sys.__stderr__`. Forced termination or permanently blocked I/O cannot guarantee
a completed drain. The [logger reference](../reference/logger.md) defines the
remaining rotation, recovery and shutdown contracts.

[Previous: Configuration composition](17-configuration-composition.md) | [Return to the series introduction](README.md)
