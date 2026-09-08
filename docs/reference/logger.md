# Unified application logging

`lclang.logger` provides `LoggerHandlerConfig`, `use_logger_handler`, and
`use_logger`. A process owns one asynchronous handler scope. Producer threads
enqueue records; one writer formats and writes console and named file sinks.
Nested/concurrent scopes are rejected. Logger wrappers select the current
process scope, and reject use outside a scope. Initialize after worker creation.

## Configuration

Python objects and mappings share the `level`, `format`, `console`, `file`,
`takeover_loggers`, and `capture_warnings` fields. No configuration files are
read by this package. CLI/Workflow adapters resolve `logger.*` through their
ordinary Frame and `-c`/`-o` layering before entering the handler scope.

`file` is a mapping of sink names. `file.default` supplies missing leaf fields
and never creates a sink. Explicit sink fields always take precedence over
the template, including False and empty collections. Thus setting
`logger.file.default.enabled: False` disables only sinks without an explicit
`enabled: True`. Override one sink directly to disable that exception:
`-o logger.file.audit.enabled "LCL[False]"`. A disabled sink does no file I/O.

Files have independent `enabled`, `directory`, `filename`, `level`, `encoding`,
`flush_interval`, `logger_names`, and `rotation` settings. Rotation supports
`none`, `size`, `time`, and `size_or_time`; intervals use positive integer
`s/m/h/d` units. Aligned rotation supports UTC `1h` and `1d`. Source names
match themselves and dot-separated descendants. Empty source lists match all.

The console defaults to INFO on stderr. Files default to INFO, UTF-8 with
backslashreplace, one-second flushing, and no rotation. An enabled file needs
a directory. Missing names become `lclang.<sink>.{pid}.log`. Templates support
`{pid}` and `{process}`. Global level defaults to NOTSET. Warnings capture is
opt-in. Verbose CLI execution lowers enabled output thresholds to DEBUG,
without enabling disabled sinks or removing source filters.
Disabled outputs retain their configured thresholds. Invalid fields include
their complete logger path; CLI diagnostics also identify the defining source
and position when available, or the owning configuration layer otherwise.

## Records and ownership

`use_logger(name=None, prefix="", emit_level=0)` selects a stdlib logger;
None selects root. Prefixes are formatter-only and appear on the first line.
`emit_level` skips additional wrapper callers through stdlib stacklevel.
Messages, arguments and exception formatting run in the writer. Queue records
are shallow copies: do not mutate referenced arguments after logging.

The root and explicitly listed takeover loggers are restored on exit. Existing
handlers are detached, never closed or reformatted. Default takeover names are
uvicorn, uvicorn.error and uvicorn.access. Other logger-specific levels and
handlers retain stdlib semantics. Streams are borrowed and never closed.

## Permanent segments and shutdown

Each file is exclusively created at its permanent path, with UTC microseconds
and a process-wide increasing sequence appended to its base name. The first
line identifies that path. Rollover creates the next segment first, then ends
the old segment with its successor path and closes it. Closed segments are
never changed, renamed, compressed, or deleted. Header bytes count toward size;
the successor footer may exceed the limit. Oversized records are never split.
Empty segments still rotate on time. Size rotation preserves time deadlines.

Scope entry fails if an enabled output cannot initialize. Normal, exceptional,
and cancelled exits stop admission, drain, flush, close, asynchronously join
the writer, and restore logging state. There is no drain timeout. Runtime sink
failures are counted and reported minimally to sys.__stderr__; other sinks
continue. Failed files recover into new segments without replaying possibly
partial writes. Hardware failures may leave gaps. Forced process termination
and permanently blocked I/O cannot guarantee delivery.

`runtime.metrics` supplies immutable aggregate and per-sink snapshots with
records_enqueued, records_written, writer_errors, rollover_count and paths.
Aggregate records_written counts a record once if any sink accepted its write;
metadata is excluded. Successful writes do not imply fsync durability.

## Service entry points

Initialize in the actual worker, before Uvicorn emits its startup messages.
Wrapping only FastAPI's lifespan starts too late and closes too early for the
server's own logging. Request tasks and background tasks can call `use_logger`
directly because admission is process-wide. Do not nest handler scopes in routes
or in a Workflow invoked by the service.

On Windows or Linux, save this as `service.py` and run `python service.py`.
FastAPI and Uvicorn are dependencies of this example application, not lclang.
The `serve` boundary can also surround an existing configured Server instance.

<!-- lclang-doc-exec -->
```python
import asyncio

import uvicorn
from fastapi import FastAPI

from lclang.logger import LoggerHandlerConfig, use_logger, use_logger_handler

app = FastAPI()


@app.get("/")
async def index():
    logger = await use_logger(name=__name__, prefix="[HTTP]")
    logger.info("request received")
    return {"ok": True}


async def serve(server, config, *, sockets=None):
    async with use_logger_handler(config):
        await server.serve(sockets=sockets)


if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_config=None))
    config = LoggerHandlerConfig(file={"service": {"directory": "./logs"}})
    asyncio.run(serve(server, config))
```

`log_config=None` lets the handler scope own logging installation. Scope exit
waits for queued server and application records, including the final server
shutdown message. Configure process spawning outside this entry point when
multiple independent Windows workers are required; each child calls `serve`.

For Linux Gunicorn, save the following as `logging_worker.py` alongside
`service.py`, install the application's `gunicorn` and `uvicorn-worker`
dependencies, and run:

```sh
gunicorn service:app --workers 4 --worker-class logging_worker.LoggingWorker --access-logfile -
```

<!-- lclang-gunicorn-exec -->
```python
import os
import signal

from uvicorn_worker import UvicornWorker

from lclang.logger import LoggerHandlerConfig, use_logger_handler


class LoggingWorker(UvicornWorker):
    def init_signals(self):
        super().init_signals()
        signal.signal(signal.SIGTERM, self.handle_exit)

    async def _serve(self):
        config = LoggerHandlerConfig(
            file={"service": {"directory": os.environ.get("LOGGER_DIRECTORY", "./logs")}}
        )
        async with use_logger_handler(config):
            await super()._serve()
```

The subclass enters the scope inside the worker's asynchronous service method,
after fork and worker initialization. The master never starts a logger writer;
Gunicorn's own handlers remain its responsibility. `LOGGER_DIRECTORY` optionally
selects the file directory. Every worker gets independent permanent paths.
Keep Gunicorn's graceful SIGTERM handler installed before entering Uvicorn.
Uvicorn restores the previous handler and replays SIGTERM after server shutdown;
the worker handler marks it no longer alive and returns so the outer logging
scope can drain and close. Leaving SIGTERM at its default action terminates the
process before that cleanup and can leave buffered log files with only a header.
The adapter depends on `uvicorn-worker`'s `_serve` hook; integration tests target
`uvicorn-worker==0.4.0` and `uvicorn==0.52.4`. Recheck this hook when upgrading
the server adapter ([worker source](https://github.com/Kludex/uvicorn-worker),
[Uvicorn server](https://github.com/Kludex/uvicorn/blob/main/uvicorn/server.py)).

The quality suite runs actual loopback HTTP, lifespan, request, background-task,
and shutdown checks with FastAPI/Uvicorn. Its Linux job additionally starts and
terminates Gunicorn using the exact worker example above. Server packages appear
only in the development integration dependency group.

## Performance measurement

Run `python -m scripts.logger_benchmark --records 1000 --threads 1 10 100` in a
development checkout. It reports call p50/p95/p99 and producer records/second
for console, file and combined output. Console targets the null device to avoid
terminal-rendering variability. Startup, thread creation, and queue drain are
outside the producer measurement. This measures admission capacity, not sustained
disk throughput; an unbounded queue can grow when producers outpace the writer.
The checked-in [measurement sample](../development/logger-benchmark.json) records
the host and Python version and is not a portable performance guarantee.
