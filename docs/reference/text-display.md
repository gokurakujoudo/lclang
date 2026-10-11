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

## Logger and CLI controls

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
