# Command-line API

`lclang.cli` is a typed async framework for Python scripts whose parameters may
come from declared defaults, `.lclcfg` files, and command-line overrides. A
decorated command handler receives one `CliContext`, including its invocation
Frame, as-of date, dry-run flag, and logging context, and returns a deterministic
`CliResult`.

The CLI resolves logging from the same final Frame as application configuration.
`CliConfig.log_config` supplies a `LoggerHandlerConfig` declaration; `.lclcfg`
settings and `-o` overrides replace the corresponding `logger.*` leaves.
`logger.console` controls the console and `logger.file.<sink>` declares named
files. `logger.file.default` supplies missing fields without creating a sink.
Explicit sink values always win over this template, regardless of which source
supplied the template. Thus a CLI default.enabled=False preserves a configured
sink's explicit enabled=True; override that sink directly to close it.

The logger scope starts after configuration is resolved and remains active
through command execution, workflow resources, and Frame cleanup. Preparation
errors go directly to stderr. Normal output drain completes before returning.
Overlapping CLI entry invocations are rejected because root logging is global.
All diagnostic console records use stderr; successful command results retain
stdout. The shared format uses UTC microseconds, level, process, thread, source
name, file/line, function, prefix and message. Each permanent file segment begins
with its absolute path. Execution audit records contain the banner, exact
redacted argv and lazy winning configuration without fixed initial positions.

`--verbose` enables runtime DEBUG diagnostics and lowers global and enabled
sink thresholds to DEBUG, retaining lower existing thresholds. Disabled sinks
stay disabled and source filters remain effective. Preparation records are not
replayed. Value rendering remains bounded and respects trailing-bang masks.
`-v/--version` retains its existing meaning.

Logger expressions can use `__as_of_date__`, `__dryrun__`, `__verbose__`,
`__ymd__`, `__execution_timestamp__`, `__command__`, and `__cli_params__`.
The date and command metadata retain the existing runtime-key semantics.
Ordinary CLI values are strings; numeric, Boolean and collection overrides use
`LCL[...]`. No logger-specific coercion is added. Unknown logger keys are errors,
including in Workflow commands where valid logger keys bypass business-input
validation. See the [logger reference](logger.md) for the complete sink contract.

Built-in commands use this same routing model. Exact valueless `-o FORCE` makes
a marked `RESULT=LCL[...]` parse strictly; ordinary override parsing remains
permissive. Invalid marked logger overrides fail when their effective field is
validated.

Dry-run remains an explicit handler decision, so the framework never pretends
to know whether an application-specific side effect is safe.


## Trusted command discovery

`lclang.cli.scan_commands(module, name, description)` imports the developer's
own trusted Python package and submodules in deterministic order. It collects
public module-level Commands, deduplicates re-exports by identity and rejects
distinct commands sharing a name. Importing developer-owned code is the intended
extension mechanism; this API is not a scanner for hostile or untrusted modules.

See the [CLI tutorial](../tutorials/09-command-line-applications.md) for a
progressive application and [workflow reference](workflow.md) for conversion.
