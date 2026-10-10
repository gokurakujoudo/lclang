# Exceptions and grouped failures

Catch the failure family whose contract your application can handle. Use
`LclError` at the outer application boundary when you need one diagnostic for
any ordinary lclang failure. Import exception types, error-code enums and
`render_failure` from `lclang.error`.

## Exception types

| Type | What it reports | Application response |
| --- | --- | --- |
| `LclError` | An ordinary library failure with a code, message and captured context. | Record the diagnostic and stop the affected operation. Application codes may be any nonempty string. |
| `LclValidationError` | Wrong input types, invalid values or conflicting declarations. `binding_names` identifies a binding conflict when present. | Correct the input or definition before trying again. Catch this type for validation; native `TypeError` and `ValueError` catches do not select it. |
| `LclStateError` | An operation unavailable in the current resource or lifecycle state. | Fix ownership or operation order. Recreate a closed scope when another run is needed. |
| `LclAttributeError` | Missing or unavailable attributes, with Python's `AttributeError` protocol. | Use explicit lookup, `hasattr`, or `getattr(value, name, default)` for optional attributes. |
| `LclFrozenAttributeError` | An attempted mutation of frozen data. It also inherits `FrozenInstanceError`. | Construct a new value instead of changing the existing snapshot. |
| `LclSyntaxError` | Malformed LCL source. | Correct the source range shown by the diagnostic. |
| `EscapeDecodeError` | Invalid literal escape content, with an exclusive content-relative `end` offset. | Normally handle the final `LclSyntaxError` from parsing. Scanner integrations can inspect `end`. |
| `InternalLiteralScanError` | A malformed literal and its exclusive absolute source offset. | Handle the final syntax diagnostic; scanner integrations retain `end` when copying errors. |
| `FStringScanError` | Invalid interpolation and its exclusive absolute source offset. | Correct braces, field syntax or literal escapes shown by the parser. |
| `LclNameError` | A required binding cannot be found. | Supply the binding in the intended scope, or use an explicitly optional lookup. |
| `LclEvaluationError` | An expression, host callback or runtime evaluation operation failed. | Inspect the concrete code, captured inputs and `__cause__` before deciding whether the operation can be retried. |
| `LclCircularDependencyError` | A dependency cycle prevents evaluation or ordering. | Remove the cycle; retrying the same graph will repeat the failure. |
| `LclClosedFrameError` | Evaluation or inspection requires a Frame that has closed. | Create a new Frame; keep borrowed Frames inside their owner's lifetime. |
| `LclConfigError` | A configuration parsing, loading or composition failure. | Inspect the complete loading route and the original cause. |
| `LclConfigSyntaxError` | Malformed `.lclcfg` declarations or embedded expressions. | Correct the retained source location. |
| `LclConfigVersionError` | Missing, invalid or unsupported configuration version metadata. | Supply the supported version declaration. |
| `LclConfigUsingError` | A source target cannot be resolved, read or loaded. | Check its path and resolver, then inspect the native cause. Optional introductions skip only a directly missing file. |
| `LclConfigCycleError` | Recursive file expansion. | Remove the cycle indicated by the loading route. |
| `LclConfigLimitError` | A configured loading budget is exceeded. | Reduce expansion or deliberately choose a suitable budget. |
| `LclConfigLifecycleError` | The loader is unavailable in its current state. | Follow its lifetime contract instead of reusing a closed loader. |
| `LclCliError` | Command binding, execution, cleanup or output failed. | Direct APIs can raise it; the CLI runner normally reports an exception result with exit status 2. |
| `LclCliUsageError` | Invalid command-line syntax or routing. | Correct the invocation using the reported command help. |
| `RouteFailure` | A routing failure with its nearest `group` and consumed `path`. | Render help for that group; preserve these fields when copying the error. |
| `LclWorkflowError` | Workflow definition, mapping, action or context failure. | Distinguish directly raised setup failures from failures recorded in execution status. |
| `WorkflowStatusStop` | A task explicitly ended in a status that stops traversal. | Inspect that task's status and description; it need not have a native cause. |
| `LclLoggerError` | Logging configuration, startup or scope lifecycle failed. | Report through a separate working channel and inspect cleanup state. Writer sink failures have their own isolation contract. |
| `LclUtilityError` | A calendar, environment, Snowflake or other utility operation failed. | Handle the specific code and retained native cause. |
| `DateOperationOutOfScopeException` | A calendar cannot resolve an operation from `source_date`; `source_calendar` identifies it. | Choose a calendar or date inside its supported scope. |
| `CalendarCannotLoadException` | A requested `calendar_id` cannot be loaded. | Check registration, loader and file contents. |
| `CalendarLogicException` | Calendar classification or generation failed for `calendar_id`. | Inspect the callback cause and affected date operation. |
| `UnappliedCalendarOperationException` | A mapping has no source calendar. | Apply the mapping to a calendar before using date operations. |
| `LclStandardError` | A standard-library function or namespace operation failed. | Correct inputs or inspect an underlying callback failure. Validation failures may use `LclValidationError` with a domain-9 code. |
| `LclErrorGroup` | Several ordinary errors, retaining Python's `ExceptionGroup` protocol. | Handle selected leaves with `except*`, `split` or `subgroup`, and keep any unhandled remainder. |

An exception class identifies the boundary or failure family. Its code identifies
the detected reason. A validation error can therefore have a language, logger,
calendar or standard-library code. An existing LCL error keeps its code while
another boundary adds source, operation or task context.

`WorkflowException` is a failure record rather than a raised exception. Its
`exception` field holds the failure; `error_task` identifies the originating task.
Failure-covering workflow contexts receive this record through `__exception__`.

## Causes, snapshots and copies

`__cause__` retains the original native exception at a wrapping boundary. The
code is selected where the operation fails, without matching message text.
Captured source, loading paths, evaluation frames and already-read values explain
the scene. Rendering does not ask the Frame for more values or reload source
files. Masked values remain redacted in these captured diagnostics. Raw causes
and Python tracebacks can still contain application data.

Awaiting is shared implementation work; the calling operation classifies its
failure. An async callback retains the callback code, and a failing async resource
close retains the cleanup code. Both preserve the original exception as their
cause.

Loading-context copies retain the concrete type, code, source span, subclass
fields, cause and traceback. Notes are copied into a separate list. Application
exception subclasses extend `copy_diagnostic_fields(target)` to retain their own
declared fields after calling the base hook. The target has already been allocated;
the hook does not rerun the exception constructor. Exception groups retain their
selected member objects and native argument sequence when split.

## How several errors arise

Errors can be nested. A resource-close group may be one member of a group that
also contains the operation failure. Read the leaves and the ownership contexts;
the outer code describes how the failures were combined.

| Boundary | Multiple failures retained together | Observable outcome |
| --- | --- | --- |
| Explicit `LclErrorGroup` construction | Application-supplied ordinary errors, including native members. | Native leaves receive LCL wrappers with their original causes. |
| Sync or async callbacks, loaders and standard helpers | A native `ExceptionGroup`, including nested groups. | Nested LCL groups retain the original topology, existing LCL codes and native causes. |
| Application `asyncio.TaskGroup` | Separate child tasks fail. | Python creates an outer native group; its leaves can already be LCL diagnostics. |
| LCL `try` / `finally` | The expression and finalizer fail. | A language group retains both failures. |
| LCL `with` | Body or later acquisition fails while earlier context exits also fail; several exits can fail. | Exits run in reverse acquisition order and groups retain each failure. |
| Frame cleanup | Several cached or retired values fail to close; the body can fail too. | Cleanup attempts all owned values; the Frame is closed and body/cleanup groups remain visible. |
| CLI construction and Frame stack | Binding setup fails while partial cleanup fails, or several owned Frames fail to close. | Direct binding/stack APIs raise groups; the CLI runner reports status 2. |
| CLI execution and output | The handler fails, cleanup fails, and writing the result can also fail. | Diagnostics retain the earlier failure groups and output failure; the runner returns status 2. |
| Workflow execution | Action or mapping fails, context finalizers fail, and task-local Frame cleanup can fail. | Status and task diagnostics retain groups; normal execution returns a result carrying the error status. |
| Scoped workflow calls | Call-body failure and owned child-Frame cleanup failure. | The call scope can raise a group while its mounted status remains available. |
| Logger scope | Startup or body failure plus stop, join, restoration or handler-close failures. | The owner attempts every cleanup stage, releases the process scope and raises the retained failures. |
| Cancellation or process control | Ordinary cleanup fails while cancellation, exit or interruption propagates. | The original control signal propagates; cleanup failures remain in its cause chain. Mixed control groups stay native. |

Sink write, timer, recovery and sink-close failures in the logging writer are
isolated: they increase `runtime.metrics.writer_errors` and use the emergency
reporting channel. They do not become a scope exception group simply because
several sinks failed. Other sinks continue according to their output contract.

## Handle groups without losing failures

`except LclError` catches an LCL group as one exception. It does not select its
members. `except* LclValidationError` selects matching leaves through nested
groups. Python propagates the unhandled remainder after the handler completes.
For explicit routing, use `split` and raise the remaining group yourself.

Handle only failures for which you have a defined recovery action. Avoid retrying
an entire action after a cleanup group: the action may have completed its side
effects before cleanup failed. Record every member through a working diagnostic
channel, then decide whether a fresh operation is appropriate. Do not suppress
`CancelledError`, `SystemExit`, `KeyboardInterrupt` or iterator termination while
handling ordinary errors.

## Select leaves and retain the remainder

Native group members are wrapped once, with their original causes. This example routes a validation leaf and leaves the cleanup failure for the outer handler.

<!-- lclang-doc-case: exceptions-manual -->

<!-- lclang-doc-exec -->
```python
from lclang.error import GeneralErrorCode, LclError, LclErrorGroup, LclValidationError

invalid = LclValidationError("port must be positive", code="APP/PORT")
native_close = OSError("socket close failed")
group = LclErrorGroup("validation and cleanup failed", [invalid, native_close])
print(group)

matched, remaining = group.split(LclValidationError)
assert isinstance(matched, LclErrorGroup) and matched.exceptions == (invalid,)
assert isinstance(remaining, LclErrorGroup)
assert remaining.exceptions[0].__cause__ is native_close
selected = group.subgroup(lambda error: isinstance(error, LclError) and error.code == GeneralErrorCode.E21_GROUP_MEMBER)
assert isinstance(selected, LclErrorGroup) and selected.exceptions == remaining.exceptions

try:
    try:
        raise group
    except* LclValidationError as errors:
        assert isinstance(errors, LclErrorGroup)
        print("Validation handled:", errors.exceptions[0].code)
except LclErrorGroup as errors:
    assert errors.exceptions == remaining.exceptions
    print("Unhandled cleanup:", errors.exceptions[0].code)
```

<!-- lclang-doc-output: stdout -->
```text
Error [LCL021910]:
Cause: validation and cleanup failed
  Failure 1:
    Error in handling failure [APP/PORT]:
    Cause: port must be positive
  Failure 2:
    Error in handling failure [LCL021811]:
    Cause: OSError: socket close failed
Validation handled: APP/PORT
Unhandled cleanup: LCL021811
```
<!-- /lclang-doc-case -->

The validation handler sees only the matching leaf. The outer handler receives the remaining LCL group. Both retain the original aggregation code; splitting also keeps each selected member object.

## Sync, async and nested callback groups

A callback can raise a native group directly, or create one through TaskGroup. Both synchronous calls and awaited results are classified by the call boundary. Existing business codes remain visible inside nested groups.

<!-- lclang-doc-case: exceptions-callbacks -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclErrorGroup, LclEvaluationError, LclValidationError
from lclang.lang import define_frame, define_module

known = LclValidationError("business rule", code="APP/RULE")
original = ExceptionGroup("callback failed", [OSError("read failed"), ExceptionGroup("nested", [known])])

def sync_callback():
    raise original

async def async_callback():
    raise original

async def task_group_callback():
    ready = asyncio.Event()
    async def fail(message):
        await ready.wait()
        raise OSError(message)
    async with asyncio.TaskGroup() as tasks:
        tasks.create_task(fail("first child"))
        tasks.create_task(fail("second child"))
        ready.set()

async def main():
    for label, callback in [("sync", sync_callback), ("async", async_callback), ("TaskGroup callback", task_group_callback)]:
        module = define_module("callbacks", {"result": "callback()"})
        async with define_frame(module, preset={"callback!": callback}) as frame:
            try:
                await frame.get("result")
            except LclErrorGroup as errors:
                assert errors.code == "LCL132811"
                assert isinstance(errors.exceptions[0], LclEvaluationError)
                assert isinstance(errors.__cause__, ExceptionGroup)
                if label != "TaskGroup callback":
                    assert errors.__cause__ is original
                    nested = errors.exceptions[1]
                    assert isinstance(nested, LclErrorGroup) and nested.exceptions == (known,)
                print(label + ":")
                print(errors)
            else:
                raise AssertionError("callback unexpectedly succeeded")

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
sync:
Error in evaluating result [LCL132811]:
  result at "<string>":1:1
    callback()
    ^^^^^^^^^^
    callback = *masked*
Cause: callback failed: ExceptionGroup: callback failed (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        callback()
        ^^^^^^^^^^
    Cause: OSError: read failed
  Failure 2:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        callback()
        ^^^^^^^^^^
    Cause: nested: ExceptionGroup: nested (1 sub-exception)
      Failure 1:
        Error in handling failure [APP/RULE]:
        Cause: business rule
async:
Error in evaluating result [LCL132811]:
  result at "<string>":1:1
    callback()
    ^^^^^^^^^^
    callback = *masked*
Cause: callback failed: ExceptionGroup: callback failed (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        callback()
        ^^^^^^^^^^
    Cause: OSError: read failed
  Failure 2:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        callback()
        ^^^^^^^^^^
    Cause: nested: ExceptionGroup: nested (1 sub-exception)
      Failure 1:
        Error in handling failure [APP/RULE]:
        Cause: business rule
TaskGroup callback:
Error in evaluating result [LCL132811]:
  result at "<string>":1:1
    callback()
    ^^^^^^^^^^
    callback = *masked*
Cause: unhandled errors in a TaskGroup: ExceptionGroup: unhandled errors in a TaskGroup (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        callback()
        ^^^^^^^^^^
    Cause: OSError: first child
  Failure 2:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        callback()
        ^^^^^^^^^^
    Cause: OSError: second child
```
<!-- /lclang-doc-case -->

The top-level code is LCL132811 for each callback. The APP/RULE leaf keeps its application code. The captured callback value is masked to keep the diagnostic deterministic and avoid exposing its representation. Inspect the native cause when recovery depends on its class; except* OSError does not match leaves already wrapped as LCL errors.

## Groups created by the application

When the application starts independent Frame requests in TaskGroup, Python owns the outer group. Its leaves are already LCL diagnostics.

<!-- lclang-doc-case: exceptions-application-task-group -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclErrorGroup, LclEvaluationError
from lclang.lang import define_frame, define_module

async def main():
    module = define_module("parallel", {"first": "1 / 0", "second": "2 / 0"})
    async with define_frame(module) as frame:
        try:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(frame.get("first"))
                tasks.create_task(frame.get("second"))
        except* LclEvaluationError as errors:
            assert isinstance(errors, ExceptionGroup) and not isinstance(errors, LclErrorGroup)
            assert len(errors.exceptions) == 2
            for error in errors.exceptions:
                assert isinstance(error, LclEvaluationError) and error.code == "LCL131421"
                print(error)

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in evaluating first [LCL131421]:
  first at "<string>":1:1
    1 / 0
    ^^^^^
Cause: ZeroDivisionError: division by zero
Error in evaluating second [LCL131421]:
  second at "<string>":1:1
    2 / 0
    ^^^^^
Cause: ZeroDivisionError: division by zero
```
<!-- /lclang-doc-case -->

The outer group is a native ExceptionGroup, so except LclError would not catch it. except* LclEvaluationError selects the two division failures. Other leaf types would propagate as the unhandled remainder.

## Expression and finalizer failure

An LCL finalizer runs while the expression failure is pending. If both fail, the group keeps both division diagnostics.

<!-- lclang-doc-case: exceptions-finalizers -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclErrorGroup
from lclang.lang import define_frame, define_module

async def main():
    module = define_module("finalizer", {"result": "try: 1 / 0 finally: 2 / 0"})
    async with define_frame(module) as frame:
        try:
            await frame.get("result")
        except LclErrorGroup as errors:
            assert errors.code == "LCL136963"
            assert [error.code for error in errors.exceptions] == ["LCL131421", "LCL131421"]
            print(errors)
        else:
            raise AssertionError("finalizer unexpectedly succeeded")

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in evaluating result [LCL136963]:
  result at "<string>":1:1
    try: 1 / 0 finally: 2 / 0
    ^^^^^^^^^^^^^^^^^^^^^^^^^
Cause: execution and cleanup failed
  Failure 1:
    Error in evaluating result [LCL131421]:
      result at "<string>":1:1
        try: 1 / 0 finally: 2 / 0
             ^^^^^
    Cause: ZeroDivisionError: division by zero
  Failure 2:
    Error in evaluating result [LCL131421]:
      result at "<string>":1:1
        try: 1 / 0 finally: 2 / 0
                            ^^^^^
    Cause: ZeroDivisionError: division by zero
```
<!-- /lclang-doc-case -->

The outer LCL136963 identifies the finalizer combination. Each leaf retains LCL131421 and the retained source expression. A successful finalizer would leave the original expression failure alone.

## Acquisition, body and context exits

A later acquisition can fail after an earlier context has entered. A failing body can also reach several failing exits. This example verifies both paths and their unwind order.

<!-- lclang-doc-case: exceptions-contexts -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclErrorGroup
from lclang.lang import define_frame, define_module

events = []

class Manager:
    def __init__(self, name, fail_enter=False):
        self.name, self.fail_enter = name, fail_enter
    def __enter__(self):
        events.append("enter " + self.name)
        if self.fail_enter:
            raise ValueError("acquire " + self.name)
        return self
    def __exit__(self, exception_type, exception, traceback):
        events.append("exit " + self.name)
        raise OSError("close " + self.name)

async def main():
    for label, source, fail_enter in [
        ("body and exits", "with first, second: 1 / 0", False),
        ("acquisition and earlier exit", "with first, second: 1", True),
    ]:
        events.clear()
        module = define_module("contexts", {"result": source})
        async with define_frame(module, preset={"first!": Manager("first"), "second!": Manager("second", fail_enter)}) as frame:
            try:
                await frame.get("result")
            except LclErrorGroup as errors:
                assert errors.code == "LCL138911"
                print(label + ":")
                print(errors)
            else:
                raise AssertionError("contexts unexpectedly succeeded")
        assert events == (["enter first", "enter second", "exit first"] if fail_enter else ["enter first", "enter second", "exit second", "exit first"])
        print("Unwind:", ", ".join(events))

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
body and exits:
Error in evaluating result [LCL138911]:
  result at "<string>":1:1
    with first, second: 1 / 0
    ^^^^^^^^^^^^^^^^^^^^^^^^^
    first = *masked*
    second = *masked*
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL138911]:
    Cause: execution and cleanup failed
      Failure 1:
        Error in evaluating result [LCL131421]:
          result at "<string>":1:1
            with first, second: 1 / 0
                                ^^^^^
            first = *masked*
            second = *masked*
        Cause: ZeroDivisionError: division by zero
      Failure 2:
        Error in handling failure [LCL138812]:
          at "<string>":1:13
            with first, second: 1 / 0
                        ^^^^^^
        Cause: OSError: close second
  Failure 2:
    Error in handling failure [LCL138812]:
      at "<string>":1:6
        with first, second: 1 / 0
             ^^^^^
    Cause: OSError: close first
Unwind: enter first, enter second, exit second, exit first
acquisition and earlier exit:
Error in evaluating result [LCL138911]:
  result at "<string>":1:1
    with first, second: 1
    ^^^^^^^^^^^^^^^^^^^^^
    first = *masked*
    second = *masked*
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL138811]:
      at "<string>":1:13
        with first, second: 1
                    ^^^^^^
    Cause: ValueError: acquire second
  Failure 2:
    Error in handling failure [LCL138812]:
      at "<string>":1:6
        with first, second: 1
             ^^^^^
    Cause: OSError: close first
Unwind: enter first, enter second, exit first
```
<!-- /lclang-doc-case -->

The failed acquisition never acquires the second manager, so only the first manager exits in that case. After a body failure, both managers exit in reverse order. Each failing exit remains visible in the nested LCL138911 groups; cleanup does not stop after the first ordinary failure.

## Cached and retired resource cleanup

Recalculation retires the prior resource snapshot. Closing the Frame attempts both the current and retired resources; a body failure remains separate from that cleanup group.

<!-- lclang-doc-case: exceptions-frame-resources -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclErrorGroup
from lclang.lang import define_frame, define_module

events = []

class Resource:
    def __init__(self, name):
        self.name = name
    async def aclose(self):
        events.append(self.name)
        raise OSError("close " + self.name)

async def main():
    count = 0
    def make():
        nonlocal count
        count += 1
        return Resource(str(count))
    module = define_module("resources", {"result": "make()"})
    frame = define_frame(module, preset={"make!": make})
    try:
        async with frame:
            assert isinstance(await frame.get("result"), Resource)
            assert isinstance(await frame.recalculate("result"), Resource)
            raise ValueError("body failed")
    except LclErrorGroup as errors:
        assert errors.code == "LCL236912"
        cleanup = errors.exceptions[1]
        assert isinstance(cleanup, LclErrorGroup) and cleanup.code == "LCL236911"
        assert len(cleanup.exceptions) == 2
        print(errors)
    else:
        raise AssertionError("cleanup unexpectedly succeeded")
    assert frame.closed and sorted(events) == ["1", "2"]
    print("Closed:", frame.closed)
    print("Resources attempted:", ", ".join(events))

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in evaluating an expression [LCL236912]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL021811]:
    Cause: ValueError: body failed
  Failure 2:
    Error in handling failure [LCL236911]:
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL236811]:
        Cause: Frame cleanup failed: OSError: close 2
      Failure 2:
        Error in handling failure [LCL236811]:
        Cause: Frame cleanup failed: OSError: close 1
Closed: True
Resources attempted: 2, 1
```
<!-- /lclang-doc-case -->

The outer LCL236912 retains the body failure and the LCL236911 cleanup group. Each failed close has LCL236811 with its original OSError cause. Both resources were attempted and the Frame is closed, so repeating close is not a retry of these operations. Use a fresh Frame for another run.

## Cancellation with several cleanup failures

The caller cancels a task while it owns two cached resources. The Frame attempts both closes and retains their failures on the original cancellation signal.

<!-- lclang-doc-case: exceptions-cancellation -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclErrorGroup, render_failure
from lclang.lang import define_frame, define_module

ready = asyncio.Event()
observed = []
closed = []

class Resource:
    def __init__(self, name):
        self.name = name
    async def aclose(self):
        closed.append(self.name)
        raise OSError("close " + self.name)

async def operation():
    frame = define_frame(define_module("cancel", {"first": "make_first()", "second": "make_second()"}), preset={"make_first!": lambda: Resource("first"), "make_second!": lambda: Resource("second")})
    try:
        async with frame:
            await frame.get("first")
            await frame.get("second")
            ready.set()
            await asyncio.Event().wait()
    except asyncio.CancelledError as signal:
        assert isinstance(signal.__cause__, LclErrorGroup)
        assert signal.__cause__.code == "LCL236911"
        assert frame.closed and closed == ["second", "first"]
        observed.append(signal)
        print(render_failure(signal, action="cancelling operation"))
        raise

async def main():
    task = asyncio.create_task(operation())
    await ready.wait()
    task.cancel("requested stop")
    try:
        await task
    except asyncio.CancelledError as signal:
        assert signal is observed[0] and task.cancelled()
        print("Caller observed cancellation:", task.cancelled())

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in cancelling operation:
Cause: CancelledError: requested stop
  Error in evaluating an expression [LCL236911]:
  Cause: execution and cleanup failed
    Failure 1:
      Error in handling failure [LCL236811]:
      Cause: Frame cleanup failed: OSError: close second
    Failure 2:
      Error in handling failure [LCL236811]:
      Cause: Frame cleanup failed: OSError: close first
Caller observed cancellation: True
```
<!-- /lclang-doc-case -->

The operation reports the cause and rethrows the cancellation. The caller observes the same exception object and a cancelled task. Cancellation has no LCL code; its cause is the LCL236911 cleanup group. Apply the same control-signal rule to SystemExit, KeyboardInterrupt and mixed BaseExceptionGroup objects instead of treating them as ordinary recoverable failures.

## Several invocation Frames fail to close

The CLI ownership component closes invocation Frames in reverse order. This direct component example uses two real cached resources whose closes fail.

<!-- lclang-doc-case: exceptions-cli-stack -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.cli.frame_stack import FrameStack
from lclang.error import LclErrorGroup
from lclang.lang import define_frame, define_module

closed = []

class Resource:
    def __init__(self, name):
        self.name = name
    async def aclose(self):
        closed.append(self.name)
        raise OSError("close " + self.name)

async def main():
    frames = []
    for name in ["first", "second"]:
        resource = Resource(name)
        frame = define_frame(define_module(name, {"resource": "make()"}), preset={"make!": lambda resource=resource: resource})
        await frame.get("resource")
        frames.append(frame)
    stack = FrameStack(tuple(frames))
    try:
        await stack.close()
    except LclErrorGroup as errors:
        assert errors.code == "LCL441971" and len(errors.exceptions) == 2
        assert [error.code for error in errors.exceptions] == ["LCL236811", "LCL236811"]
        print(errors)
    else:
        raise AssertionError("stack unexpectedly closed successfully")
    assert stack.closed and all(frame.closed for frame in frames)
    assert closed == ["second", "first"]
    await stack.close()
    print("Frames closed:", all(frame.closed for frame in frames))
    print("Close order:", ", ".join(closed))

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in command-line usage [LCL441971]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL236811]:
    Cause: Frame cleanup failed: OSError: close second
  Failure 2:
    Error in handling failure [LCL236811]:
    Cause: Frame cleanup failed: OSError: close first
Frames closed: True
Close order: second, first
```
<!-- /lclang-doc-case -->

The outer LCL441971 identifies the CLI stack combination. Its leaves retain their original Frame cleanup codes, LCL236811. Both Frames are closed and a second stack close does not repeat the failed operations. The normal CliEntrance runner owns this stack and converts ordinary failures to exit status 2.

## Construction and partial invocation cleanup

This static configuration contains an empty definition. The example injects a failure after the real partial invocation Frame closes, so both setup and cleanup failures can be observed.

<!-- lclang-doc-case: exceptions-cli-construction -->

<!-- lclang-doc-file: broken.lclcfg -->
```lclcfg
__LCL_VERSION__: 1
value:
```

<!-- lclang-doc-exec -->
```python
import asyncio
from datetime import date
from unittest.mock import patch

from lclang.cli import CliConfig, CliContext, CliParams, CliResult, Command
from lclang.cli.frame_binding import build_binding
from lclang.error import LclErrorGroup
from lclang.lang import Frame

closed = []
original_close = Frame.close

async def close_then_fail(frame):
    await original_close(frame)
    closed.append(frame)
    raise OSError("partial invocation cleanup")

async def handler(context: CliContext) -> CliResult:
    return CliResult.success("unreachable")

async def main():
    command = Command("run", "Run", [], {}, handler)
    params = CliParams("python", ["run"], date(2026, 1, 1), False, "broken.lclcfg", {})
    with patch.object(Frame, "close", close_then_fail):
        try:
            await build_binding(command, params, CliConfig())
        except LclErrorGroup as errors:
            assert errors.code == "LCL441972"
            assert errors.exceptions[0].code == "LCL311482"
            assert errors.exceptions[1].code == "LCL441811"
            print(errors)
        else:
            raise AssertionError("binding unexpectedly succeeded")
    assert closed and all(frame.closed for frame in closed)
    print("Partial Frames closed:", len(closed))

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in command-line usage [LCL441972]:
Cause: execution and cleanup failed
  Failure 1:
    Error in loading config file "broken.lclcfg" [LCL311482]:
      at "broken.lclcfg":2:1
        value:
        ^^^^^^
    Cause: definition requires an expression
  Failure 2:
    Error in handling failure [LCL441811]:
    Cause: OSError: partial invocation cleanup
Partial Frames closed: 1
```
<!-- /lclang-doc-case -->

LCL441972 combines the configuration syntax error and the partial Frame close error. The source fixture is displayed above the Python program and is loaded exactly as shown. Direct build_binding raises the group; CliEntrance reports the ordinary failure with status 2. The injected close calls the original first, preserving the real final resource state.

## Handler, Frame cleanup and result output

The handler fails, each of the three invocation Frames closes and reports a failure, and result output fails too. A standard logging filter removes raw Python tracebacks; the structured diagnostic messages are emitted through the real console sink.

<!-- lclang-doc-case: exceptions-cli-execution -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging
from contextlib import redirect_stderr
from unittest.mock import patch

from lclang.cli import CliConfig, CliContext, CliEntrance, CliResult, Command, CommandGroup
from lclang.lang import Frame
from lclang.logger import LoggerHandlerConfig

class DiagnosticOnly(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True

closed = []
original_close = Frame.close

async def close_then_fail(frame):
    if frame.closed:
        return
    await original_close(frame)
    closed.append(frame)
    raise OSError("invocation Frame close")

def fail_output(*args, **kwargs):
    raise OSError("result output")

async def handler(context: CliContext) -> CliResult:
    raise ValueError("handler failed")

async def main():
    logs, stderr = io.StringIO(), io.StringIO()
    config = CliConfig(LoggerHandlerConfig(format="%(message)s", console={"stream": logs}))
    entrance = CliEntrance(CommandGroup("root", "Root", [Command("run", "Run", [], {}, handler)]), cli_config=config)
    target = logging.getLogger("lclang.cli.command_execution")
    filter = DiagnosticOnly()
    target.addFilter(filter)
    try:
        with patch.object(Frame, "close", close_then_fail), patch("lclang.cli.command_execution.write_result", fail_output), redirect_stderr(stderr):
            status = await entrance.run(["python", "tool.py", "run"])
    finally:
        target.removeFilter(filter)
    assert status == 2 and all(frame.closed for frame in closed)
    assert len(closed) == 3
    text = logs.getvalue()
    assert "LCL451811" in text and "LCL441971" in text and "LCL451813" in text
    assert "command output failed after another failure" in text
    print(text, end="")
    print("Exit status:", status)
    print("Invocation Frames closed:", len(closed))

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in executing command [LCL451811]:
Cause: ValueError: handler failed
Error in cleaning up command [LCL451911]:
Cause: command execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL451811]:
    Cause: ValueError: handler failed
  Failure 2:
    Error in handling failure [LCL441971]:
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL441971]:
        Cause: execution and cleanup failed
          Failure 1:
            Error in handling failure [LCL441811]:
            Cause: OSError: invocation Frame close
          Failure 2:
            Error in handling failure [LCL441811]:
            Cause: OSError: invocation Frame close
      Failure 2:
        Error in handling failure [LCL441811]:
        Cause: OSError: invocation Frame close
Error in writing command output [LCL451911]:
Cause: command output failed after another failure
  Failure 1:
    Error in handling failure [LCL451911]:
    Cause: command execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL451811]:
        Cause: ValueError: handler failed
      Failure 2:
        Error in handling failure [LCL441971]:
        Cause: execution and cleanup failed
          Failure 1:
            Error in handling failure [LCL441971]:
            Cause: execution and cleanup failed
              Failure 1:
                Error in handling failure [LCL441811]:
                Cause: OSError: invocation Frame close
              Failure 2:
                Error in handling failure [LCL441811]:
                Cause: OSError: invocation Frame close
          Failure 2:
            Error in handling failure [LCL441811]:
            Cause: OSError: invocation Frame close
  Failure 2:
    Error in handling failure [LCL451813]:
    Cause: OSError: result output
Exit status: 2
Invocation Frames closed: 3
```
<!-- /lclang-doc-case -->

The log contains the handler failure, the execution/cleanup combination and the later output combination. LCL451911 keeps the earlier groups rather than replacing them with LCL451813. The runner returns status 2 and all owned Frames are closed. Use that returned status at the process boundary. The DiagnosticOnly filter is optional; remove it to include native traceback frames, which can contain application data. Avoid retrying the whole command without knowing which side effects completed.

## Logger startup and handler cleanup

The writer cannot start, then handler cleanup reports another failure. The injected close calls the actual handler close before raising, so cleanup state is still observable.

<!-- lclang-doc-case: exceptions-logger-startup -->

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from unittest.mock import patch

from lclang.error import LclErrorGroup
from lclang.logger import use_logger, use_logger_handler
from lclang.logger.queue_handler import LocalQueueHandler

original_close = LocalQueueHandler.close

def close_then_fail(handler):
    original_close(handler)
    raise OSError("handler close")

async def main():
    handlers = logging.root.handlers
    with patch("lclang.logger.runtime_registry.Thread.start", side_effect=OSError("writer startup")), patch.object(LocalQueueHandler, "close", close_then_fail):
        try:
            async with use_logger_handler({"console": {"enabled": False}}):
                raise AssertionError("startup must not enter")
        except LclErrorGroup as errors:
            assert errors.code == "LCL622911"
            assert [error.code for error in errors.exceptions] == ["LCL625811", "LCL622811"]
            print(errors)
        else:
            raise AssertionError("startup unexpectedly succeeded")
    assert logging.root.handlers is handlers
    async with use_logger_handler({"console": {"enabled": False}}):
        await use_logger()
    print("Handlers restored:", logging.root.handlers is handlers)
    print("Scope reusable:", True)

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in logging [LCL622911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL625811]:
    Cause: OSError: writer startup
  Failure 2:
    Error in handling failure [LCL622811]:
    Cause: OSError: handler close
Handlers restored: True
Scope reusable: True
```
<!-- /lclang-doc-case -->

The group combines startup code LCL625811 with cleanup code LCL622811 under LCL622911. The body never runs. The process scope is released and another scope can be initialized. Report this failure through stdout, stderr or another working channel rather than the logger that failed to start.

## Logger body, stop, join, restoration and close

Each case fails the body and one cleanup phase. The final case fails all four phases. Each injected fault runs the original operation first, including joining the writer and restoring borrowed logging state.

<!-- lclang-doc-case: exceptions-logger-cleanup -->

<!-- lclang-doc-exec -->
```python
import asyncio
import logging
from contextlib import ExitStack
from unittest.mock import patch

from lclang.error import LclError, LclErrorGroup
from lclang.logger import use_logger, use_logger_handler
from lclang.logger.logging_takeover import LoggingTakeover
from lclang.logger.queue_handler import LocalQueueHandler

original_stop = LocalQueueHandler.stop
original_restore = LoggingTakeover.restore
original_close = LocalQueueHandler.close

def stop(handler):
    original_stop(handler)
    raise OSError("stop")

def restore(takeover):
    original_restore(takeover)
    raise OSError("restore")

def close(handler):
    original_close(handler)
    raise OSError("close")

def leaves(error):
    if isinstance(error, LclErrorGroup):
        return [leaf for member in error.exceptions for leaf in leaves(member)]
    assert isinstance(error, LclError)
    return [error]

async def main():
    handlers = logging.root.handlers
    for phase in ["stop", "join", "restore", "close", "all"]:
        runtime = None
        try:
            with ExitStack() as patches:
                async with use_logger_handler({"console": {"enabled": False}}) as runtime:
                    original_join = runtime.thread.join
                    def join():
                        original_join()
                        raise OSError("join")
                    operations = [("stop", LocalQueueHandler, "stop", stop), ("join", runtime.thread, "join", join), ("restore", LoggingTakeover, "restore", restore), ("close", LocalQueueHandler, "close", close)]
                    for name, owner, attribute, replacement in operations:
                        if phase == name or phase == "all":
                            patches.enter_context(patch.object(owner, attribute, replacement))
                    raise ValueError("scope body")
        except LclErrorGroup as errors:
            assert errors.code == "LCL622911"
            failures = leaves(errors)
            assert len(failures) == (5 if phase == "all" else 2)
            assert failures[0].code == "LCL021811"
            assert all(error.code == "LCL622811" for error in failures[1:])
            print(phase + ":")
            print(errors)
        else:
            raise AssertionError("cleanup unexpectedly succeeded")
        assert runtime is not None and not runtime.thread.is_alive() and not runtime.started
        assert logging.root.handlers is handlers
        async with use_logger_handler({"console": {"enabled": False}}):
            await use_logger()
    print("Handlers restored:", logging.root.handlers is handlers)
    print("All scopes reusable:", True)

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
stop:
Error in logging [LCL622911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL021811]:
    Cause: ValueError: scope body
  Failure 2:
    Error in handling failure [LCL622811]:
    Cause: OSError: stop
join:
Error in logging [LCL622911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL021811]:
    Cause: ValueError: scope body
  Failure 2:
    Error in handling failure [LCL622811]:
    Cause: OSError: join
restore:
Error in logging [LCL622911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL021811]:
    Cause: ValueError: scope body
  Failure 2:
    Error in handling failure [LCL622811]:
    Cause: OSError: restore
close:
Error in logging [LCL622911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL021811]:
    Cause: ValueError: scope body
  Failure 2:
    Error in handling failure [LCL622811]:
    Cause: OSError: close
all:
Error in logging [LCL622911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL622911]:
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL622911]:
        Cause: execution and cleanup failed
          Failure 1:
            Error in handling failure [LCL622911]:
            Cause: execution and cleanup failed
              Failure 1:
                Error in handling failure [LCL021811]:
                Cause: ValueError: scope body
              Failure 2:
                Error in handling failure [LCL622811]:
                Cause: OSError: stop
          Failure 2:
            Error in handling failure [LCL622811]:
            Cause: OSError: join
      Failure 2:
        Error in handling failure [LCL622811]:
        Cause: OSError: restore
  Failure 2:
    Error in handling failure [LCL622811]:
    Cause: OSError: close
Handlers restored: True
All scopes reusable: True
```
<!-- /lclang-doc-case -->

Every phase is attempted even after an earlier ordinary failure. Nested LCL622911 groups retain the body and every LCL622811 cleanup failure in encounter order. The writer has stopped and the process scope is reusable. An existing body-only native exception retains its native type when cleanup succeeds; aggregation wraps native ordinary members so their causes remain selectable through LCL leaves.

## Several writer sink failures stay isolated

The console write and final close fail while the file sink remains usable. The emergency channel reports the failures, and the scope returns normally with diagnostic metrics.

<!-- lclang-doc-case: exceptions-logger-metrics -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lclang.logger import use_logger, use_logger_handler
from lclang.logger.console_sink import ConsoleSink

original_close = ConsoleSink.close

def write_fail(sink, record):
    raise OSError("console write")

def close_fail(sink):
    original_close(sink)
    raise OSError("console close")

async def main(directory):
    emergency = io.StringIO()
    with patch.object(ConsoleSink, "write", write_fail), patch.object(ConsoleSink, "close", close_fail), patch("sys.__stderr__", emergency):
        async with use_logger_handler({"format": "%(message)s", "console": {"stream": io.StringIO()}, "file": {"app": {"directory": directory}}}) as runtime:
            logger = await use_logger(name="metrics-example")
            logger.info("file survives")
    assert runtime.metrics.writer_errors == 2
    assert runtime.metrics.records_written == 1
    text = next(Path(directory).glob("*.log")).read_text(encoding="utf-8")
    assert "file survives" in text
    print(emergency.getvalue(), end="")
    print("Writer errors:", runtime.metrics.writer_errors)
    print("Records written:", runtime.metrics.records_written)
    print("File message:", next(line for line in text.splitlines() if line == "file survives"))

with TemporaryDirectory() as directory:
    asyncio.run(main(directory))
```

<!-- lclang-doc-output: stdout -->
```text
Error in writing log sink 'console' [LCL635811]:
Cause: OSError: console write
Error in writing log sink 'console' [LCL635811]:
Cause: OSError: console close
Writer errors: 2
Records written: 1
File message: file survives
```
<!-- /lclang-doc-case -->

These are isolated writer errors rather than a raised scope group. The file received the record and writer_errors counts both console failures. Check metrics when output delivery matters. A failed record is not automatically replayed; retrying business work to reproduce a log can duplicate its effects.

## Workflow action, mapping, acquisition and task cleanup

Four runs exercise action groups, evaluated mapping groups, a later context acquisition group and owned task Frame cleanup. Earlier contexts still exit in reverse order. The standard logging handler emits the actual workflow diagnostics; its filter removes raw tracebacks.

<!-- lclang-doc-case: exceptions-workflow-unwind -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from unittest.mock import patch

from lclang.error import LclError, LclErrorGroup, WorkflowException
from lclang.lang import Frame, define_frame, define_module
from lclang.workflow import ExecutionStatus, ExecutionStatusManager, TaskContext, WorkflowExecutionContext, define_context_task, define_task, define_variable, define_workflow

@dataclass
class Value:
    value: int

class DiagnosticOnly(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True

def leaves(error):
    if isinstance(error, LclErrorGroup):
        return [leaf for member in error.exceptions for leaf in leaves(member)]
    assert isinstance(error, LclError)
    return [error]

def make_logger(stream):
    logger = logging.getLogger("workflow-errors-example")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(DiagnosticOnly())
    logger.addHandler(handler)
    return logger, handler

async def run_case(mode):
    stream = io.StringIO()
    logger, handler = make_logger(stream)
    events = []
    owned = []
    original_close = Frame.close

    async def fail():
        raise ExceptionGroup("mapping input", [ValueError("first"), OSError("second")])

    @asynccontextmanager
    async def scope(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> AsyncIterator[Value]:
        if mode == "acquire" and args.value == 1:
            raise ExceptionGroup("context acquisition", [OSError("open"), ValueError("validate")])
        events.append("enter " + str(args.value))
        if context.frame not in owned:
            owned.append(context.frame)
        try:
            yield args
        finally:
            events.append("exit " + str(args.value))
            raise OSError("context exit " + str(args.value))

    async def action(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        events.append("action")
        raise ExceptionGroup("action", [ValueError("business"), OSError("remote")])

    async def close(frame):
        await original_close(frame)
        if mode == "frame" and frame in owned:
            raise OSError("task Frame close")

    variable = define_variable[int]("bad")
    task = define_task("root", "Root", task_action=action, args_mapping=Value(variable.quote if mode == "mapping" else 0), context_tasks=[define_context_task("outer", "Outer", scope, Value(0)), define_context_task("inner", "Inner", scope, Value(1))])
    workflow = define_workflow("Failures", task)
    try:
        async with define_frame(define_module("inputs", {"bad": "fail()"}), preset={"fail!": fail}) as frame:
            with patch.object(Frame, "close", close):
                result = await workflow.execute(WorkflowExecutionContext(False, date(2026, 1, 1), False, logger, frame))
            assert result.execution_status.status is ExecutionStatus.ERROR
            assert not frame.closed
            record = await frame.get("__exception__")
            assert isinstance(record, WorkflowException)
            failures = leaves(record.exception)
            if mode == "mapping":
                assert [error.code for error in failures] == ["LCL132811", "LCL132811", "LCL532812", "LCL532812"]
                assert "action" not in events
            elif mode == "acquire":
                assert [error.code for error in failures] == ["LCL532811", "LCL532811", "LCL532812"]
                assert "action" not in events
            else:
                expected = ["LCL531811", "LCL531811", "LCL532812", "LCL532812"]
                assert [error.code for error in failures] == expected + (["LCL532813"] if mode == "frame" else [])
            assert all(error.__cause__ is not None for error in failures)
            assert all(item.closed for item in owned)
            print(mode + ":")
            print(stream.getvalue(), end="")
            print("Status:", result.execution_status.status.value)
            print("Unwind:", ", ".join(events))
            print("Task Frames closed:", all(item.closed for item in owned))
    finally:
        logger.removeHandler(handler)
        handler.close()

async def main():
    for mode in ["action", "mapping", "acquire", "frame"]:
        await run_case(mode)

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
action:
Error in running workflow task 'root' [LCL531811]:
Context: workflow task root
Cause: action: ExceptionGroup: action (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL531811]:
    Cause: ValueError: business
  Failure 2:
    Error in handling failure [LCL531811]:
    Cause: OSError: remote
  task status: ERROR
Error in running workflow task 'root.inner' [LCL535911]:
Context: workflow task root.inner
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL531811]:
    Context: workflow task root
    Cause: action: ExceptionGroup: action (2 sub-exceptions)
      Failure 1:
        Error in handling failure [LCL531811]:
        Cause: ValueError: business
      Failure 2:
        Error in handling failure [LCL531811]:
        Cause: OSError: remote
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 1
  task status: ERROR
task complete: [root.inner] ERROR
Error in running workflow task 'root.outer' [LCL535911]:
Context: workflow task root.outer
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL535911]:
    Context: workflow task root.inner
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL531811]:
        Context: workflow task root
        Cause: action: ExceptionGroup: action (2 sub-exceptions)
          Failure 1:
            Error in handling failure [LCL531811]:
            Cause: ValueError: business
          Failure 2:
            Error in handling failure [LCL531811]:
            Cause: OSError: remote
      Failure 2:
        Error in handling failure [LCL532812]:
        Cause: OSError: context exit 1
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 0
  task status: ERROR
task complete: [root.outer] ERROR
task complete: [root] ERROR
Status: ERROR
Unwind: enter 0, enter 1, action, exit 1, exit 0
Task Frames closed: True
mapping:
Error in evaluating bad [LCL132811]:
  bad at "<string>":1:1
    fail()
    ^^^^^^
    fail = *masked*
Context: workflow mapping value <- bad
Context: workflow task root
Cause: mapping input: ExceptionGroup: mapping input (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        fail()
        ^^^^^^
    Cause: ValueError: first
  Failure 2:
    Error in handling failure [LCL132811]:
      at "<string>":1:1
        fail()
        ^^^^^^
    Cause: OSError: second
  task status: ERROR
Error in running workflow task 'root.inner' [LCL535911]:
Context: workflow task root.inner
Cause: execution and cleanup failed
  Failure 1:
    Error in evaluating bad [LCL132811]:
      bad at "<string>":1:1
        fail()
        ^^^^^^
        fail = *masked*
    Context: workflow mapping value <- bad
    Context: workflow task root
    Cause: mapping input: ExceptionGroup: mapping input (2 sub-exceptions)
      Failure 1:
        Error in handling failure [LCL132811]:
          at "<string>":1:1
            fail()
            ^^^^^^
        Cause: ValueError: first
      Failure 2:
        Error in handling failure [LCL132811]:
          at "<string>":1:1
            fail()
            ^^^^^^
        Cause: OSError: second
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 1
  task status: ERROR
task complete: [root.inner] ERROR
Error in running workflow task 'root.outer' [LCL535911]:
Context: workflow task root.outer
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL535911]:
    Context: workflow task root.inner
    Cause: execution and cleanup failed
      Failure 1:
        Error in evaluating bad [LCL132811]:
          bad at "<string>":1:1
            fail()
            ^^^^^^
            fail = *masked*
        Context: workflow mapping value <- bad
        Context: workflow task root
        Cause: mapping input: ExceptionGroup: mapping input (2 sub-exceptions)
          Failure 1:
            Error in handling failure [LCL132811]:
              at "<string>":1:1
                fail()
                ^^^^^^
            Cause: ValueError: first
          Failure 2:
            Error in handling failure [LCL132811]:
              at "<string>":1:1
                fail()
                ^^^^^^
            Cause: OSError: second
      Failure 2:
        Error in handling failure [LCL532812]:
        Cause: OSError: context exit 1
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 0
  task status: ERROR
task complete: [root.outer] ERROR
task complete: [root] ERROR
Status: ERROR
Unwind: enter 0, enter 1, exit 1, exit 0
Task Frames closed: True
acquire:
Error in running workflow task 'root.inner' [LCL532811]:
Context: workflow task root.inner
Cause: context acquisition: ExceptionGroup: context acquisition (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL532811]:
    Cause: OSError: open
  Failure 2:
    Error in handling failure [LCL532811]:
    Cause: ValueError: validate
  task status: ERROR
task complete: [root.inner] ERROR
Error in running workflow task 'root.outer' [LCL535911]:
Context: workflow task root.outer
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL532811]:
    Context: workflow task root.inner
    Cause: context acquisition: ExceptionGroup: context acquisition (2 sub-exceptions)
      Failure 1:
        Error in handling failure [LCL532811]:
        Cause: OSError: open
      Failure 2:
        Error in handling failure [LCL532811]:
        Cause: ValueError: validate
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 0
  task status: ERROR
task complete: [root.outer] ERROR
task complete: [root] ERROR
Status: ERROR
Unwind: enter 0, exit 0
Task Frames closed: True
frame:
Error in running workflow task 'root' [LCL531811]:
Context: workflow task root
Cause: action: ExceptionGroup: action (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL531811]:
    Cause: ValueError: business
  Failure 2:
    Error in handling failure [LCL531811]:
    Cause: OSError: remote
  task status: ERROR
Error in running workflow task 'root.inner' [LCL535911]:
Context: workflow task root.inner
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL531811]:
    Context: workflow task root
    Cause: action: ExceptionGroup: action (2 sub-exceptions)
      Failure 1:
        Error in handling failure [LCL531811]:
        Cause: ValueError: business
      Failure 2:
        Error in handling failure [LCL531811]:
        Cause: OSError: remote
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 1
  task status: ERROR
task complete: [root.inner] ERROR
Error in running workflow task 'root.outer' [LCL535911]:
Context: workflow task root.outer
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL535911]:
    Context: workflow task root.inner
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL531811]:
        Context: workflow task root
        Cause: action: ExceptionGroup: action (2 sub-exceptions)
          Failure 1:
            Error in handling failure [LCL531811]:
            Cause: ValueError: business
          Failure 2:
            Error in handling failure [LCL531811]:
            Cause: OSError: remote
      Failure 2:
        Error in handling failure [LCL532812]:
        Cause: OSError: context exit 1
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: context exit 0
  task status: ERROR
task complete: [root.outer] ERROR
Error in running workflow task 'root' [LCL535911]:
Context: workflow task root
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL535911]:
    Context: workflow task root.outer
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL535911]:
        Context: workflow task root.inner
        Cause: execution and cleanup failed
          Failure 1:
            Error in handling failure [LCL531811]:
            Context: workflow task root
            Cause: action: ExceptionGroup: action (2 sub-exceptions)
              Failure 1:
                Error in handling failure [LCL531811]:
                Cause: ValueError: business
              Failure 2:
                Error in handling failure [LCL531811]:
                Cause: OSError: remote
          Failure 2:
            Error in handling failure [LCL532812]:
            Cause: OSError: context exit 1
      Failure 2:
        Error in handling failure [LCL532812]:
        Cause: OSError: context exit 0
  Failure 2:
    Error in handling failure [LCL532813]:
    Cause: OSError: task Frame close
  task status: ERROR
task complete: [root] ERROR
Status: ERROR
Unwind: enter 0, enter 1, action, exit 1, exit 0
Task Frames closed: True
```
<!-- /lclang-doc-case -->

Normal execute returns an ERROR result for these ordinary failures. Inspect execution_status and the WorkflowException record from the borrowed Frame; except LclError around execute alone will not observe these recorded failures. The mapping leaves retain their language code, while native action and context failures receive workflow codes. Every owned task Frame closes; the caller retains ownership of the shared Frame. The frame case injects its failure after the real close. Treat each run as failed and reconcile completed side effects before creating a fresh run.

## Dynamic workflow body and call Frame cleanup

The child executes successfully, then processing its result fails and its owned call Frame reports a close failure. The parent action inspects the group locally and rethrows it for normal workflow status recording.

<!-- lclang-doc-case: exceptions-workflow-call -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from unittest.mock import patch

from lclang.error import LclError, LclErrorGroup, WorkflowException
from lclang.lang import Frame, define_frame, define_module
from lclang.workflow import ExecutionStatus, ExecutionStatusManager, TaskContext, WorkflowExecutionContext, define_context_task, define_task, define_variable, define_workflow

@dataclass
class Value:
    value: int

class DiagnosticOnly(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True

def leaves(error):
    if isinstance(error, LclErrorGroup):
        return [leaf for member in error.exceptions for leaf in leaves(member)]
    assert isinstance(error, LclError)
    return [error]

def make_logger(stream):
    logger = logging.getLogger("workflow-errors-example")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(DiagnosticOnly())
    logger.addHandler(handler)
    return logger, handler

async def main():
    stream = io.StringIO()
    logger, handler = make_logger(stream)
    calls = []
    original_close = Frame.close

    async def child_action(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        return args

    child = define_workflow("Child", define_task("child", "Child", task_action=child_action, args_mapping=Value(7)))

    async def close(frame):
        await original_close(frame)
        if frame in calls:
            raise OSError("call Frame close")

    async def parent_action(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        try:
            with patch.object(Frame, "close", close):
                async with child.execute_in_task(context, status_mgr, name="nested") as result:
                    calls.append(result.execution_frame)
                    assert result.execution_status.status is ExecutionStatus.SUCCESS
                    assert not result.execution_frame.closed
                    raise ValueError("result processing")
        except LclErrorGroup as errors:
            assert errors.code == "LCL535911"
            assert [error.code for error in leaves(errors)] == ["LCL541812", "LCL541813"]
            assert calls[0].closed
            # Inspect locally, then preserve the failure for the parent's status.
            raise
        return args

    workflow = define_workflow("Parent", define_task("root", "Root", task_action=parent_action, args_mapping=Value(0)))
    try:
        async with define_frame() as frame:
            result = await workflow.execute(WorkflowExecutionContext(False, date(2026, 1, 1), False, logger, frame))
            assert result.execution_status.status is ExecutionStatus.ERROR
            record = await frame.get("__exception__")
            assert isinstance(record, WorkflowException) and record.exception.code == "LCL535911"
            assert not frame.closed
            print(stream.getvalue(), end="")
            print("Parent status:", result.execution_status.status.value)
            print("Call Frame closed:", calls[0].closed)
            print("Borrowed parent open:", not frame.closed)
    finally:
        logger.removeHandler(handler)
        handler.close()

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in calling workflow 'root.nested' [LCL535911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL541812]:
    Cause: ValueError: result processing
  Failure 2:
    Error in handling failure [LCL541813]:
    Cause: OSError: call Frame close
workflow call complete: [root.nested] Child ERROR
Error in running workflow task 'root' [LCL535911]:
Context: workflow task root
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL541812]:
    Cause: ValueError: result processing
  Failure 2:
    Error in handling failure [LCL541813]:
    Cause: OSError: call Frame close
  task status: ERROR
task complete: [root] ERROR
Parent status: ERROR
Call Frame closed: True
Borrowed parent open: True
```
<!-- /lclang-doc-case -->

The scoped call raises LCL535911 with LCL541812 for result processing and LCL541813 for cleanup. Its result Frame is usable only inside the call scope and is closed afterwards. The outer execute returns ERROR and retains the same group under __exception__. A child ERROR result can be inspected inside the scope without a raised body failure; always inspect status before consuming outputs. The call result later becomes ERROR when cleanup fails.

## Failure handling and release both fail

A FailureCoveringContextTask acquires a resource, receives a business group, fails while handling it and fails again while releasing. The final group retains each business leaf once.

<!-- lclang-doc-case: exceptions-workflow-covering -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from unittest.mock import patch

from lclang.error import LclError, LclErrorGroup, WorkflowException
from lclang.lang import Frame, define_frame, define_module
from lclang.workflow import ExecutionStatus, ExecutionStatusManager, TaskContext, WorkflowExecutionContext, define_context_task, define_task, define_variable, define_workflow

@dataclass
class Value:
    value: int

class DiagnosticOnly(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True

def leaves(error):
    if isinstance(error, LclErrorGroup):
        return [leaf for member in error.exceptions for leaf in leaves(member)]
    assert isinstance(error, LclError)
    return [error]

def make_logger(stream):
    logger = logging.getLogger("workflow-errors-example")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(DiagnosticOnly())
    logger.addHandler(handler)
    return logger, handler

from lclang.workflow import FailureCoveringContextTask

class Recovery(FailureCoveringContextTask[Value, Value]):
    async def acquire(self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        return args

    async def handle_exception(self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager, resource: Value, exception: Exception) -> None:
        assert isinstance(exception, LclErrorGroup)
        raise OSError("recovery handler")

    async def release(self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager, resource: Value) -> None:
        raise OSError("recovery release")

async def action(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
    raise ExceptionGroup("business", [ValueError("first"), OSError("second")])

async def main():
    stream = io.StringIO()
    logger, handler = make_logger(stream)
    task = define_task("root", "Root", task_action=action, args_mapping=Value(0), context_tasks=[define_context_task("recover", "Recovery", Recovery(), Value(0))])
    try:
        async with define_frame() as frame:
            result = await define_workflow("Recovery", task).execute(WorkflowExecutionContext(False, date(2026, 1, 1), False, logger, frame))
            assert result.execution_status.status is ExecutionStatus.ERROR
            record = await frame.get("__exception__")
            assert isinstance(record, WorkflowException)
            assert [error.code for error in leaves(record.exception)] == ["LCL531811", "LCL531811", "LCL533811", "LCL532812"]
            print(stream.getvalue(), end="")
            print("Status:", result.execution_status.status.value)
    finally:
        logger.removeHandler(handler)
        handler.close()

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in running workflow task 'root' [LCL531811]:
Context: workflow task root
Cause: business: ExceptionGroup: business (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL531811]:
    Cause: ValueError: first
  Failure 2:
    Error in handling failure [LCL531811]:
    Cause: OSError: second
  task status: ERROR
Error in running workflow task 'root.recover' [LCL535911]:
Context: workflow task root.recover
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL535911]:
    Cause: execution and cleanup failed
      Failure 1:
        Error in handling failure [LCL531811]:
        Context: workflow task root
        Cause: business: ExceptionGroup: business (2 sub-exceptions)
          Failure 1:
            Error in handling failure [LCL531811]:
            Cause: ValueError: first
          Failure 2:
            Error in handling failure [LCL531811]:
            Cause: OSError: second
      Failure 2:
        Error in handling failure [LCL533811]:
        Cause: OSError: recovery handler
  Failure 2:
    Error in handling failure [LCL532812]:
    Cause: OSError: recovery release
  task status: ERROR
task complete: [root.recover] ERROR
task complete: [root] ERROR
Status: ERROR
```
<!-- /lclang-doc-case -->

Return from handle_exception only when every selected failure has been dealt with. Re-raise an unhandled remainder, as in the except* example above. A successful handler and release mark FAILURE_COVERED; that status still stops dependent traversal. Here the handler and release fail, so the result is ERROR, and codes LCL533811 and LCL532812 identify the two later operations. Release runs even when handling or a control signal fails.

## Mixed native control groups at the process boundary

A mixed BaseExceptionGroup requests exit while also carrying an ordinary business failure. Frame cleanup fails too. The operation reports every member, preserves the original group and rethrows it.

<!-- lclang-doc-case: exceptions-control-group exit=2 -->

<!-- lclang-doc-exec -->
```python
import asyncio

from lclang.error import LclError, render_failure
from lclang.lang import define_frame, define_module

signal = SystemExit(2)
business = OSError("business")
original = BaseExceptionGroup("shutdown", [signal, business])
closed = []

class Resource:
    async def aclose(self):
        closed.append("resource")
        raise OSError("close")

async def operation():
    frame = define_frame(define_module("shutdown", {"resource": "make()"}), preset={"make!": Resource})
    try:
        async with frame:
            await frame.get("resource")
            raise original
    except BaseExceptionGroup as errors:
        assert errors is original and errors.exceptions == (signal, business)
        assert isinstance(errors.__cause__, LclError) and errors.__cause__.code == "LCL236811"
        assert frame.closed and closed == ["resource"]
        print(render_failure(errors, action="stopping application"))
        raise

try:
    asyncio.run(operation())
except BaseExceptionGroup as errors:
    exits, remainder = errors.split(SystemExit)
    assert exits is not None and exits.exceptions == (signal,)
    assert remainder is not None and remainder.exceptions == (business,)
    # All failures were reported above; honor the requested process exit.
    print("Exit requested:", signal.code)
    raise SystemExit(signal.code)
```

<!-- lclang-doc-output: stdout -->
```text
Error in stopping application:
Cause: BaseExceptionGroup: shutdown (2 sub-exceptions)
  Error in evaluating an expression [LCL236811]:
  Cause: Frame cleanup failed: OSError: close
  Failure 1:
    Error in handling failure:
    Cause: SystemExit: 2
  Failure 2:
    Error in handling failure [LCL022890]:
    Cause: OSError: business
Exit requested: 2
```
<!-- /lclang-doc-case -->

The process boundary selects the requested SystemExit after all failures have been reported, then exits with status 2. A mixed group keeps its native type and identity; an except Exception handler will not catch it. Keep controls out of LclErrorGroup. In a reusable library scope, propagate the mixed group to its owner instead of choosing a process exit there. A group containing KeyboardInterrupt or cancellation requires the corresponding interruption policy.

## Application exception fields survive copies

An application subclass stores a public job identifier and extends the diagnostic copy hook. The copy retains its native cause and starts with an independent notes list.

<!-- lclang-doc-case: exceptions-copy-extension -->

<!-- lclang-doc-exec -->
```python
from copy import copy

from lclang.error import LclError, LclValidationError

class JobError(LclError):
    def __init__(self, message, *, job_id):
        super().__init__(message, code="APP/JOB")
        self.job_id = job_id

    def copy_diagnostic_fields(self, target):
        super().copy_diagnostic_fields(target)
        assert isinstance(target, JobError)
        target.job_id = self.job_id

error = JobError("job failed", job_id="job-7")
error.__cause__ = OSError("storage")
error.add_note("attempt 1")
copied = copy(error)
assert copied is not error and copied.job_id == "job-7"
assert copied.code == "APP/JOB" and copied.__cause__ is error.__cause__
copied.add_note("inspected copy")
assert error.__notes__ == ["attempt 1"]
try:
    error.copy_diagnostic_fields(LclError("incompatible"))
except LclValidationError as failure:
    assert failure.code == "LCL011183"
else:
    raise AssertionError("incompatible target accepted")
print(copied)
print("Original notes:", error.__notes__)
```

<!-- lclang-doc-output: stdout -->
```text
Error [APP/JOB]:
Context: attempt 1
Context: inspected copy
Cause: job failed: OSError: storage
Original notes: ['attempt 1']
```
<!-- /lclang-doc-case -->

Call the parent hook first, then copy explicitly declared fields. The parent rejects an incompatible target with LCL011183. No instance dictionary access is needed. Copying keeps the original cause object and captured records; avoid altering shared cause exceptions during recovery.

## Native groups from loaders and public helpers

A custom resolver fails after reading the declared fixture. A host text implementation and an awaited utility callback also raise native groups. Each API reports its own boundary code and keeps the two original causes.

<!-- lclang-doc-case: exceptions-loader-helpers -->

<!-- lclang-doc-file: settings.lclcfg -->
```lclcfg
__LCL_VERSION__: 1
value: 2
```

<!-- lclang-doc-exec -->
```python
import asyncio
from pathlib import Path

from lclang.config import ConfigLoader, ResolvedConfigSource
from lclang.error import LclError, LclErrorGroup, LclStandardError, LclUtilityError
from lclang.lang.stdlib import lines
from lclang.utils import invoke

def native_group():
    return ExceptionGroup("host operations", [OSError("first"), ValueError("second")])

class Resolver:
    async def resolve(self, path: Path, *, importer: ResolvedConfigSource | None) -> ResolvedConfigSource:
        assert path.read_text(encoding="utf-8") == "__LCL_VERSION__: 1\nvalue: 2\n"
        raise native_group()

class HostText(str):
    def splitlines(self, *, keepends=False):
        raise native_group()

async def callback():
    raise native_group()

def report(errors, code, leaf_type):
    assert errors.code == code and len(errors.exceptions) == 2
    assert all(isinstance(error, leaf_type) for error in errors.exceptions)
    assert [type(error.__cause__) for error in errors.exceptions] == [OSError, ValueError]
    print(errors)

async def main():
    loader = ConfigLoader(Resolver())
    try:
        await loader.load(Path("settings.lclcfg"))
    except LclErrorGroup as errors:
        assert errors.config_stack and errors.__cause__ is not None
        report(errors, "LCL323931", LclError)
    try:
        lines(HostText("data"))
    except LclErrorGroup as errors:
        report(errors, "LCL961890", LclStandardError)
    try:
        await invoke(callback)
    except LclErrorGroup as errors:
        report(errors, "LCL771811", LclUtilityError)

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in loading config file "settings.lclcfg" [LCL323931]:
Cause: cannot load config source settings.lclcfg: ExceptionGroup: host operations (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL323931]:
    Cause: OSError: first
  Failure 2:
    Error in handling failure [LCL323931]:
    Cause: ValueError: second
Error in a standard-library operation [LCL961890]:
Context: lclang operation lines
Cause: host operations: ExceptionGroup: host operations (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL961890]:
    Cause: OSError: first
  Failure 2:
    Error in handling failure [LCL961890]:
    Cause: ValueError: second
Error in a utility operation [LCL771811]:
Context: lclang operation invoke
Cause: host operations: ExceptionGroup: host operations (2 sub-exceptions)
  Failure 1:
    Error in handling failure [LCL771811]:
    Cause: OSError: first
  Failure 2:
    Error in handling failure [LCL771811]:
    Cause: ValueError: second
```
<!-- /lclang-doc-case -->

The resolver group retains its loading route under LCL323931. The text helper and utility invocation report LCL961890 and LCL771811 with their own leaf types. Their groups preserve the native topology. Handle selected LCL leaves and inspect __cause__ when recovery depends on OSError or ValueError. This example reports every group at its boundary; a reusable adapter should rethrow any unhandled leaves.

## CLI logger setup and invocation cleanup

The configuration creates an owned console stream. Logger startup fails before the command runs, then closing the invocation Frame reports a stream-close failure. Both are reported by the actual CLI runner.

<!-- lclang-doc-case: exceptions-cli-logger-setup -->

<!-- lclang-doc-file: startup.lclcfg -->
```lclcfg
__LCL_VERSION__: 1
logger.console.stream: make_stream()
```

<!-- lclang-doc-exec -->
```python
import asyncio
import io
from contextlib import redirect_stderr
from threading import Thread
from unittest.mock import patch

from lclang.cli import CliContext, CliEntrance, CliResult, CommandGroup, cli

streams = []
original_start = Thread.start

class Stream(io.StringIO):
    def close(self):
        super().close()
        raise OSError("owned stream close")

def make_stream():
    stream = Stream()
    streams.append(stream)
    return stream

def fail_start(thread):
    if thread.name == "lclang.logger.writer":
        raise OSError("logger startup")
    original_start(thread)

@cli.command(preset={"make_stream": make_stream})
async def unused_command(context: CliContext) -> CliResult:
    raise AssertionError("handler must not run")

entrance = CliEntrance(CommandGroup("root", "Root", [unused_command]))
diagnostic = io.StringIO()
with patch.object(Thread, "start", fail_start), redirect_stderr(diagnostic):
    status = asyncio.run(entrance.run(["python", "tool.py", "unused", "-c", "startup.lclcfg"]))
assert status == 2 and len(streams) == 1 and streams[0].closed
assert all(code in diagnostic.getvalue() for code in ["LCL451911", "LCL625811", "LCL236811"])
print(diagnostic.getvalue(), end="")
print("Status:", status)
print("Owned stream closed:", streams[0].closed)
```

<!-- lclang-doc-output: stdout -->
```text
Error in executing command [LCL451911]:
Cause: execution and cleanup failed
  Failure 1:
    Error in handling failure [LCL625811]:
    Cause: OSError: logger startup
  Failure 2:
    Error in handling failure [LCL236811]:
    Cause: Frame cleanup failed: OSError: owned stream close
Status: 2
Owned stream closed: True
```
<!-- /lclang-doc-case -->

LCL451911 combines logger startup code LCL625811 and the retained Frame close code LCL236811. The handler never runs, the stream is closed and the CLI returns status 2. A stream calculated by an LCL definition belongs to its Frame; a stream passed through typed framework configuration remains borrowed, as described in the CLI reference. Do not write another diagnostic to the failed stream.

## Iterator termination inside native groups

An action raises a native ExceptionGroup containing StopAsyncIteration and an ordinary failure. Recovery does not receive the control group, release still runs and its failure remains in the original group cause.

<!-- lclang-doc-case: exceptions-iterator-controls -->

<!-- lclang-doc-exec -->
```python
import asyncio
import io
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from unittest.mock import patch

from lclang.error import LclError, LclErrorGroup, WorkflowException
from lclang.lang import Frame, define_frame, define_module
from lclang.workflow import ExecutionStatus, ExecutionStatusManager, TaskContext, WorkflowExecutionContext, define_context_task, define_task, define_variable, define_workflow

@dataclass
class Value:
    value: int

class DiagnosticOnly(logging.Filter):
    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True

def leaves(error):
    if isinstance(error, LclErrorGroup):
        return [leaf for member in error.exceptions for leaf in leaves(member)]
    assert isinstance(error, LclError)
    return [error]

def make_logger(stream):
    logger = logging.getLogger("workflow-errors-example")
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(DiagnosticOnly())
    logger.addHandler(handler)
    return logger, handler

from lclang.error import render_failure
from lclang.workflow import FailureCoveringContextTask

signal = StopAsyncIteration("done")
business = OSError("business")
original = ExceptionGroup("iterator request", [signal, business])
events = []
owned = []

class Recovery(FailureCoveringContextTask[Value, Value]):
    async def acquire(self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
        owned.append(context.frame)
        return args

    async def handle_exception(self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager, resource: Value, exception: Exception) -> None:
        raise AssertionError("controls must not enter ordinary recovery")

    async def release(self, context: TaskContext, args: Value, status_mgr: ExecutionStatusManager, resource: Value) -> None:
        events.append("release")
        raise OSError("release")

async def action(context: TaskContext, args: Value, status_mgr: ExecutionStatusManager) -> Value:
    raise original

async def main():
    stream = io.StringIO()
    logger, handler = make_logger(stream)
    task = define_task("root", "Root", task_action=action, args_mapping=Value(0), context_tasks=[define_context_task("recover", "Recovery", Recovery(), Value(0))])
    try:
        async with define_frame() as frame:
            try:
                await define_workflow("Iterator", task).execute(WorkflowExecutionContext(False, date(2026, 1, 1), False, logger, frame))
            except ExceptionGroup as errors:
                assert errors is original and errors.exceptions == (signal, business)
                assert isinstance(errors.__cause__, LclError) and errors.__cause__.code == "LCL532812"
                print(render_failure(errors, action="ending workflow"))
                completed, remaining = errors.split(StopAsyncIteration)
                assert completed is not None and completed.exceptions == (signal,)
                assert remaining is not None and remaining.exceptions == (business,)
                # This owner expects iterator completion, but retains the business failure.
                try:
                    raise remaining
                except ExceptionGroup as unhandled:
                    print(render_failure(unhandled, action="reporting remaining failure"))
                assert events == ["release"] and owned[0].closed and not frame.closed
                print("Task Frame closed:", owned[0].closed)
                print("Iterator completion observed:", True)
            else:
                raise AssertionError("control group was converted to a workflow result")
    finally:
        logger.removeHandler(handler)
        handler.close()

asyncio.run(main())
```

<!-- lclang-doc-output: stdout -->
```text
Error in ending workflow:
Cause: ExceptionGroup: iterator request (2 sub-exceptions)
  Error in executing a workflow [LCL532812]:
  Cause: OSError: release
  Failure 1:
    Error in handling failure:
    Cause: StopAsyncIteration: done
  Failure 2:
    Error in handling failure [LCL022890]:
    Cause: OSError: business
Error in reporting remaining failure [LCL022890]:
Cause: ExceptionGroup: iterator request (1 sub-exception)
  Error in executing a workflow [LCL532812]:
  Cause: OSError: release
  Failure 1:
    Error in handling failure [LCL022890]:
    Cause: OSError: business
Task Frame closed: True
Iterator completion observed: True
```
<!-- /lclang-doc-case -->

ExceptionGroup inherits Exception, so a broad except Exception alone cannot distinguish this group from an ordinary failure. The library preserves its type and identity and returns no workflow result. This application owner expects the iterator completion, selects it explicitly and reports the remaining business failure. A reusable component should rethrow an unhandled remainder. Native controls have no ordinary diagnostic code; the OSError leaf and retained cleanup cause do. Python still converts StopIteration escaping a coroutine and iteration signals escaping an async generator into RuntimeError where its protocol requires that conversion.
