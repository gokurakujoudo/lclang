# Command-line API

Workflow variable defaults occupy a separate lowest-priority binding environment.
`Command.default_bindings` retains these declarations without evaluating them;
each invocation owns fresh factory caches. Existing entrance, preset, parameter,
configuration, and CLI precedence is unchanged. Help marks defaulted variables
optional, safely renders fixed values (including `None`), and displays factories
as `<factory>`. A dataclass field fallback also makes a workflow input optional
when all of its unresolved uses have a field fallback. These field fallbacks
apply only to their mapping locations and do not create LCL bindings.

`lclang.cli` is a typed async framework for Python scripts whose parameters may
come from declared defaults, `.lclcfg` files, and command-line overrides. A
decorated command handler receives one `CliContext`, including its invocation
Frame, as-of date, dry-run flag, and logging context, and returns a deterministic
`CliResult`.

`CliEntrance(group, lcl_mixin={"service": service})` supplies shared host values
and callables to every command routed through the entrance, including commands
inside nested groups and workflows converted with `to_cli()`. The entrance
copies the mapping shallowly at definition time; the referenced objects remain
shared. Binding names are validated and trailing `!` markers retain masking.

Each invocation combines these defaults with the selected command's host preset
before config expressions and logger settings are evaluated. Precedence is
entrance `lcl_mixin`, command/workflow preset, parameter defaults, config, then
CLI overrides, with later layers winning. Workflow `lcl_mixin` is part of its
command preset and therefore wins over entrance defaults. Host helpers do not
automatically become CLI parameters. Dynamic `using` targets keep the loader's
existing scope and do not receive host presets.

Original command definitions remain unchanged. Invocations own separate Frames
and caches, while supplied objects retain their ordinary shared Python state.
Running a command directly with `command.run()` does not apply entrance bindings.

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


## Parameter help

Command help groups documented parameters by their full parent scope, with
unqualified names in a first `(global)` block. Scopes and rows sort alphabetically
(ignoring case), and rows retain full names for copying into `-o` overrides.
Type annotations omit the `collections.abc.` prefix, including nested types.

Static defaults make an input optional and appear as `default=...`. Help uses
the same precedence as execution: entrance bindings, command/workflow presets,
then declared parameter defaults. A preset entry containing `None`, `False`,
zero, or an empty container is still a default. `ParameterDoc.default=None`
retains its existing meaning of no declared default. Defaults use bounded,
single-line representations; masked values appear as `*masked*`.

Help never loads the selected `-c` file, evaluates configuration expressions,
initializes logging, or runs the command. Extra host helpers are not parameters.

## Trusted command discovery

`lclang.cli.scan_commands(module, name, description)` imports the developer's
own trusted Python package and submodules in deterministic order. It collects
public module-level Commands, deduplicates re-exports by identity and rejects
distinct commands sharing a name. Importing developer-owned code is the intended
extension mechanism; this API is not a scanner for hostile or untrusted modules.

See the [CLI tutorial](../tutorials/09-command-line-applications.md) for a
progressive application and [workflow reference](workflow.md) for conversion.
