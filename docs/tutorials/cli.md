# Build a CLI in a Python script

`lclang.cli` is a typed framework for Python scripts whose parameters come from
defaults, `.lclcfg` files, and command-line overrides. It has no third-party
runtime dependency. Configuration is trusted application code, not a sandbox
for hostile expressions.

## A complete script

The root `CommandGroup` describes the application but is not a command-line
segment. A decorated async handler receives one `CliContext` and returns one
`CliResult`.

<!-- lclang-cli-exec -->
```python
import asyncio

from lclang.cli import (
    CliContext,
    CliEntrance,
    CliResult,
    CommandGroup,
    ParameterDoc,
    cli,
)


@cli.command(
    parameter_docs=[
        ParameterDoc("message", str, True, "Message to display", "Hello from lclang")
    ]
)
async def greet_command(context: CliContext) -> CliResult:
    """Display the configured greeting.

    :param context: Current CLI invocation.
    :returns: Successful command result.
    """
    message = await context.frame.get("message")
    return CliResult.success(f"{message} (as of {context.as_of_date.isoformat()})")


root = CommandGroup("root", "Greeting tools", [greet_command])
application = CliEntrance(root, version="1.0.0")
status = asyncio.run(
    application.run(
        ["python", "greeting.py", "greet", "--as-of", "20260809"]
    )
)
assert status == 0
```

Output:

```text
Hello from lclang (as of 2026-08-09)
```

In a real script, replace the explicit token list with
`asyncio.run(application.run())`. The ambient adapter creates full argv as
`[sys.executable, *sys.argv]`.

## Command-line model

Every invocation is parsed as:

```text
<python executable> <script.py> [<command_group> ...] <command> [options]
```

Command and group names are lowercase `snake_case` and matched exactly. The root
group name is descriptive only. Common options are:

- `-c, --config <file>` loads one `.lclcfg` file.
- `-o, --override <key> [<value>]` is repeatable; the last value for a key wins.
  Without a value it stores boolean `True`. A following `-o` or `--override`
  always begins another override and can never become the preceding value.
- `-a, --as-of <YYYYMMDD>` sets a strict calendar date; local today is default.
- `-wif, --dryrun` tells the handler to avoid side effects when it supports that.
- `-h, --help` displays root, group, or command help.
- `-v, --version` displays the version at the root.

Explicit help and version do not load configuration, build Frames, create log
directories, or call a handler. Missing/unknown commands and invalid options
return status `2` and render nearest-scope help on stderr.

## Parameter methodology and precedence

`ParameterDoc` documents a Frame binding. `required=True` checks that the name
exists after layering; it does not evaluate or type-convert the value.
`value_type` is help text only. The handler owns semantic validation when it
fetches the value.

Each invocation owns this lazy hierarchy, from lowest to highest precedence:

```text
LCL_IMPORTS(preset)
  -> command and logging defaults
  -> config file
  -> CLI overrides
  -> cli-runtime
```

The handler fetches values with `await context.frame.get("name")`. Cached values
remain snapshots for that invocation, and every created Frame is closed when the
command finishes.

## Static configuration and lazy overrides

Suppose `common.lclcfg` contains:

```lcl
prefix: "Hello "
target: "world"
```

and `application.lclcfg` contains:

```lcl
using "common.lclcfg"
message: prefix + target
```

Run the command with the configuration value:

```console
python greeting.py greet --config application.lclcfg
```

A normal override is always a literal host-provided string:

```console
python greeting.py greet -c application.lclcfg -o message "literal message"
```

A key without a value is an external host-provided boolean `True`:

```console
python greeting.py greet -o enabled
```

Thus `-o first -o second value` means `first=True` and `second="value"`.
Other option-looking tokens still remain literal values when they occupy the
value slot; only `-o` and `--override` are reserved override boundaries.

A whole, successfully parsed `LCL[...]` token stores a lazy LCL expression:

```console
python greeting.py greet -c application.lclcfg -o message "LCL[prefix + 'team']"
```

An empty or malformed marker remains literal host-provided text. Static Frame
inspection reports these values as `ExternalProvided`; only valid `LCL[...]`
markers are non-evaluated definitions. `as_of_date`, `dryrun`, and `cli_params`
are reserved runtime bindings and cannot be overridden.

## Dryrun is a handler policy

The framework still loads configuration, constructs Frames, configures logging,
and calls the handler in dryrun mode. Guard the actual external operation:

```python
if context.dryrun:
    return CliResult.success("would send the greeting")
await send_greeting(await context.frame.get("message"))
return CliResult.success("greeting sent")
```

Unit tests should mock `send_greeting`, use static config strings declared with
the case, and prove that the mock is skipped only when the handler checks dryrun.

## Logging

File logging is disabled by default. Set these names in `.lclcfg` or through
overrides: `log_dir`, `log_file_name`, `log_level`, and `log_format`. For example:

```console
python greeting.py greet -o log_dir ./logs -o log_level DEBUG
```

The logger is isolated from the root logger, appends UTF-8, and is closed after
the command. The percent-style format must retain time, filename, line, function,
message, and raw logging arguments; exception tracebacks are appended. Tests put
enabled log directories under an automatically cleaned temporary directory.

## Results and failures

`SUCCESS` is exit `0` and writes its description to stdout. `FAILURE` is exit `1`
and writes stderr. `EXCEPTION` and caught ordinary exceptions are exit `2` and
write stderr; caught exceptions also include a traceback in the log. Cancellation,
`KeyboardInterrupt`, and `SystemExit` propagate after best-effort cleanup.

Handlers use `CliResult.success(message)` and `CliResult.fail(message)` as concise
constructors for the corresponding status values:

```python
if not await context.frame.get("message"):
    return CliResult.fail("message cannot be empty")
return CliResult.success("message accepted")
```

Use `Command.run(full_argv)` for a command-level unit test and
`CliEntrance.run(full_argv)` for routing/integration tests. Pass token arrays
directly—never reconstruct shell quoting in a test.

## Built-in lclang module commands

The package itself is an entrance with three commands. `builtins` prints every
canonical LCL builtin with stable descriptions:

```console
python -m lclang.cli builtins
```

Ordinary functions and values use one list level. Reviewed namespace methods
appear immediately below their namespace with two-space indentation:

```text
- recursive: Build a variadic eager fixed point.
- text: Unicode text helpers.
  - join: Join sync or async string items.
  - lines: Split text at Unicode line boundaries.
```

Top-level names are sorted; namespace methods retain their reviewed manifest
order. The command performs no LCL evaluation and requires no `RESULT`.

By default, `parse_lcl` prints the existing side-effect-free variable inspection
tree without evaluating `RESULT`:

```console
python -m lclang.cli parse_lcl -o a 100 -o b 200 -o RESULT "LCL[a+b]"
```

Its first line describes `RESULT` as `a + b (NotEvaluated)` and its two child
lines describe external-provided string values `'100'` and `'200'`. A direct
literal result is likewise external-provided:

```console
python -m lclang.cli parse_lcl -o RESULT 100
```

```text
- RESULT@cli_runtime/cli_overrides: (ExternalProvided) str: '100'
```

Dependencies resolved from lclang's reviewed canonical layers use
`NativeProvided`. Every function and namespace uses the same concise grammar,
while CLI literals remain external:

```text
len@.../LCL_BUILTINS: (NativeProvided) Builtin Function: len
iter@.../LCL_ROOT: (NativeProvided) Builtin Namespace: iter
```

Add the valueless `EVAL` override to evaluate first and then render cached
values:

```console
python -m lclang.cli parse_lcl -o RESULT "LCL[1 + 2]" -o EVAL
```

```text
- RESULT@cli_runtime/cli_overrides: 1 + 2 (Cached) int: 3
```

If evaluation fails, `parse_lcl -o EVAL` still returns the cached inspection
tree, including the structured failure and its variable evaluation stack. The
ordinary mode remains non-evaluating.

`eval_lcl` evaluates the same binding exactly once:

```console
python -m lclang.cli eval_lcl -o a 100 -o b 200 -o RESULT "LCL[a+b]"
```

Output:

```text
100200
```

Evaluation failures identify the complete variable-owner route. For example, a
failure inside a `quicksort` LCL function called by `RESULT` ends with:

```text
[variable evaluation stack: RESULT -> quicksort]
```

A malformed or incomplete `LCL[...]` token deliberately remains a literal
string for compatibility. If `quicksort` contains such a token,
`parse_lcl` shows it as `(ExternalProvided) str: ...`; calling it from `RESULT`
then reports `TypeError: 'str' object is not callable` with
`[variable evaluation stack: RESULT]`. Use `parse_lcl` first when a complex
command unexpectedly reports a non-callable string.

All three commands accept the normal config, override, date, dryrun, help,
version, and logging options. `RESULT` is required by `parse_lcl` and `eval_lcl`;
other dependency names may be supplied without `ParameterDoc` declarations
through a config file or `-o`.
