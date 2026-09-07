# Command-line API

`lclang.cli` is a typed async framework for Python scripts whose parameters may
come from declared defaults, `.lclcfg` files, and command-line overrides. A
decorated command handler receives one `CliContext`, including its invocation
Frame, as-of date, dry-run flag, and logging context, and returns a deterministic
`CliResult`.

The framework provides immutable invocation values, nested command groups,
structured help, full-argument parsing, platform-neutral process entry points,
alphabetized configuration-parameter help, isolated formal file logging, and
opt-in internal tracing. Logger settings use scoped configuration names such as
`logger.log_dir`. Non-error application records print to stdout, application
errors print to stderr, and `--verbose` adds `DEBUG` records to stdout,
independently of file logging. File and terminal application records share the
configured structured format, including time, level, source location,
function, and message; the default no longer appends logging argument tuples.
Logger expressions can use the reserved values `__as_of_date__`, `__dryrun__`,
`__verbose__`, `__ymd__`, `__execution_timestamp__`, and `__command__`; public
Python constants provide every runtime key, including `__cli_params__`. Enabled
file logs begin
with four readable audit records: their bound path, a centered multi-line
execution banner, exact JSON argv with masked override redaction, and sorted,
aligned winning configuration. The configuration audit renders lazy LCL source
without evaluating expressions or warming caches. Pass `--verbose` after a
selected command to trace expression parsing, value provenance, caching, fallbacks, and
evaluation to stderr; enabled file logging receives the same records. Trace
values use bounded representations. A trailing `!` on a definition or binding
key, such as `api_token!: load_token()`, keeps the runtime name `api_token` but
renders its parse, evaluation, lookup, cache, failure, and inspection payloads
as `*masked*`. The marker is exact-name and sticky across overrides; derived
keys require their own marker. Application-authored log messages remain the
handler's responsibility. The existing `-v/--version` spelling remains the
version command. Precedence rises from preset and command defaults through
configuration definitions and command-line overrides to reserved runtime
values. Built-in commands inventory available values, parse LCL, and evaluate
LCL using the same routing model. Exact valueless `-o FORCE` makes a marked
`RESULT=LCL[...]` parse strictly and reports a source-aligned status-2 syntax
diagnostic; ordinary and non-RESULT override parsing remains permissive.

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
