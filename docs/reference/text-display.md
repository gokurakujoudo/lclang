# Text diagnostics and dependency trees

Verbose logs, exceptions, variable inspection and CLI trees share tree connectors,
source positions and protected value summaries. Definitions use
`name: expression (location)`. Cached, external and shared values are leaves:
`name: (type) value (source)`. Arguments and native values retain their own source
labels. Unknown provenance is displayed as `unknown`; it is never inferred.

Runtime trees contain dependencies that actually ran, sorted by
`(name.casefold(), name)`. Static inspection includes static dependencies and marks
unevaluated definitions. Cached inspection nodes stop expansion; their structured
fields still retain the static children. Workflow trees retain execution order.

Verbose events are DEBUG records displayed as VERBOSE by the framework formatter.
The default verbose prefix retains the timestamp, process and thread. Root requests
produce one complete successful runtime tree. First failures show a short reason,
failure identifier and execution context; exception output expands the failing
path and its already-read value leaves. Source excerpts appear only at the
innermost failure. Logging never evaluates extra branches or reloads sources.

Failure propagation produces one summary per failure at the end of a root request,
with the names of bindings whose failure caches were actually committed. Individual
propagation relations and cache owners remain in detached record context. A root
that recovers is not described as failed. Cache hits and shared returns stay explicit.

Exception trees show the explicit Cause before expanding the diagnostic stack.
An unsuppressed handling context takes that position when there is no explicit
cause. Python traceback trees follow the same order. Stack frames, notes and
exception-group members retain their original evidence and ordering.

Every human diagnostic error code has its short reason on the same line. Failure
identifiers correlate verbose summaries, cache returns and exception output.
`repr(error)` is a protected single-line summary; `str(error)` is the full tree.
Ordinary LCL values and canonical `to_source` keep their existing meaning.

Successful evaluations emit one completion event, followed by one tree for the
root request. Dynamic using targets emit a single resolution event with the
target path, declaration location and evaluation ID. Their expressions and
dependencies remain in detached record metadata. Failed targets retain the
expression, read values and loading route in the exception tree.

Exception groups share identical evaluation prefixes and branch in member order.
Failure IDs correlate reports; they do not suppress new evidence added by a
wrapper. Each distinct failure retains its cause and innermost source excerpt.
Python callables show their actual implementation's code location when available.
Diagnostics do not open Python source files to locate a callable.

## Logger and CLI controls

### Unhandled application exceptions

`install_exception_hooks(*, traceback_style="compact", include_threads=True,
loop=None)` installs explicit stderr reporting. Import it from `lclang.logger`.
The returned `ExceptionHookInstallation.restore()` restores only handlers still
owned by that installation. Native exceptions and control signals delegate to
the previous handler. Passing a loop selects that loop alone; install and restore
its handler on the loop's owning thread.

Install hooks at application startup and keep them active until Python reports
an uncaught failure. Restoring in a `finally` block before the failure reaches
`sys.excepthook` would disable that report. Applications that catch failures can
use `LclExceptionFormatter` instead. CLI already reports caught failures at its
execution boundary and does not install these hooks.

<!-- lclang-doc-exec -->
```python
import io
import sys
from contextlib import redirect_stderr

from lclang.error import LclError
from lclang.logger import install_exception_hooks

previous = sys.excepthook
installation = install_exception_hooks(include_threads=False)
output = io.StringIO()
try:
    try:
        raise LclError("billing failed", code="APP/BILLING")
    except LclError as error:
        original_trace = error.__traceback__
        with redirect_stderr(output):
            sys.excepthook(type(error), error, original_trace)
        assert error.__traceback__ is original_trace
finally:
    installation.restore()
assert sys.excepthook is previous
assert "[APP/BILLING: billing failed]" in output.getvalue()
assert "Python traceback:" in output.getvalue()
```

The hook and logger formatter show the LCL tree first, then application and
external-library Python frames. Compact mode removes language implementation
frames by module identity. Full mode restores them. Both leave the exception's
original traceback, cause, context and group members available to the caller.

`LoggerHandlerConfig.traceback_style` accepts `"compact"` (default) or `"full"`.
The same field is available in mappings, `logger.traceback_style` in LCL and CLI
`-o logger.traceback_style full`. Compact tracebacks omit lclang Python frames by
module identity and retain application and external-library frames. Full mode
retains all Python frames. Both modes retain native chains and group members,
without repeating complete LCL diagnostics or changing original exceptions.

External logging callers can install `LclExceptionFormatter` on their own handler.
It accepts standard formatter arguments and keyword `traceback_style`. Borrowing
a logger through `use_verbose` never installs a formatter or changes handlers.
`LogRecord.levelno` and the original `levelname` remain DEBUG. The stable verbose,
stage, evaluation, failure and context extras support external filtering; tree
records include detached tree data for external formatting.

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging

from lclang.error import LclError
from lclang.lang import define_frame, define_module
from lclang.logger import LclExceptionFormatter, use_verbose


async def main() -> None:
    output = io.StringIO()
    logger = logging.Logger("pricing", logging.DEBUG)
    handler = logging.StreamHandler(output)
    handler.setFormatter(LclExceptionFormatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    module = define_module("pricing", {"RESULT": "total + 1", "total": "subtotal / divisor"})
    async with define_frame(module, preset={"subtotal": 39, "divisor": 0}) as frame:
        with use_verbose(logger):
            try:
                await frame.get("RESULT")
            except LclError as error:
                failure_id = error.verbose_failure_id
                assert failure_id is not None
                logger.exception("Pricing request failed")
                try:
                    await frame.get("total")
                except LclError as cached:
                    assert cached is error and cached.verbose_failure_id == failure_id
            else:
                raise AssertionError("The zero divisor must fail")
    text = output.getvalue()
    assert "VERBOSE Failed while evaluating total [LCL131421: division by zero]" in text
    assert text.count("Error in evaluating RESULT") == 1
    assert "Returned the cached failure of total; no new evaluation" in text
    assert "Could not evaluate RESULT" in text
    assert text.count("Cached failures: total, RESULT") == 1
    assert "Could not complete" not in text
    assert "Reason:" not in text
    assert "total: subtotal / divisor (" in text


asyncio.run(main())
```

The first verbose failure explains the arithmetic stage and requesting context.
The root summary lists `total` and `RESULT` after both failure caches have committed.
The explicit exception record adds the full failed dependency path and retained
value snapshots. Both use the same failure identifier; the later cache read adds
a short reference. The logger and its handler belong to this application.

`eval_lcl` retains value stdout. Add `-o TREE` for the actual runtime tree.
`parse_lcl` shows static inspection; `-o EVAL` shows the actual evaluated tree,
including ordinary failures, with its existing successful inspection exit status.
Cached and shared roots remain leaves in either runtime tree mode.

CLI execution and cleanup failures are reported together after cleanup. Stderr
receives one complete diagnostic. File output adds Python stack evidence and
short LCL references. A later output failure is reported separately and references
the earlier failure. Native cancellation and protocol controls still propagate.
