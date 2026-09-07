# Command-line applications

`lclang.cli` is a typed async framework for Python scripts whose parameters may
come from declared defaults, `.lclcfg` files, and command-line overrides. The
handler receives one invocation Frame and returns one process-compatible result.

## What you will learn

- how to declare a typed command and route it through an entrance;
- how config, defaults, and overrides become Frame bindings;
- how to expose expected output and exit status;
- why dry-run behavior remains an explicit handler decision.

## Build one complete command

The root `CommandGroup` describes the application but is not a command-line
segment. A decorated async handler receives exactly one `CliContext`.
Configuration parameter rows are rendered in case-insensitive A-Z order, so
help remains easy to scan even when declarations follow business data flow.

<!-- lclang-doc-exec -->
```python
import asyncio
import io
from contextlib import redirect_stdout

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
        ParameterDoc("message", str, True, "Message to display", "Hello")
    ]
)
async def greet_command(context: CliContext) -> CliResult:
    """Display the configured greeting."""
    message = await context.frame.get("message")
    return CliResult.success(
        f"{message} (as of {context.as_of_date.isoformat()})"
    )


root = CommandGroup("root", "Greeting tools", [greet_command])
application = CliEntrance(root, version="1.0.0")
output = io.StringIO()
with redirect_stdout(output):
    status = asyncio.run(
        application.run(
            ["python", "greeting.py", "greet", "--as-of", "20260809"]
        )
    )

assert status == 0
assert output.getvalue() == "Hello (as of 2026-08-09)\n"
```

The declared default supplies `Hello` because no config or override replaces
`message`. Argument parsing converts `20260809` to the invocation date, the
handler combines both values, and `CliResult.success` writes the asserted line
to stdout while mapping to status `0`.

In a real process, call `application.run()` without an explicit token list. The
adapter uses the current executable and `sys.argv`. Tests should pass exact
token arrays so shell quoting never becomes part of the unit under test.

## Layer configuration, override, and dry-run policy

The next command loads derived text from a temporary config, overrides one
dependency, and asks the handler to describe rather than perform its side
effect.

<!-- lclang-doc-exec -->
```python
import asyncio
import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from lclang.cli import (
    CliContext,
    CliEntrance,
    CliResult,
    CommandGroup,
    ParameterDoc,
    cli,
)


@cli.command(
    parameter_docs=[ParameterDoc("message", str, True, "Message to send")]
)
async def send_command(context: CliContext) -> CliResult:
    """Send or preview one configured message."""
    message = await context.frame.get("message")
    prefix = "would send" if context.dryrun else "sent"
    return CliResult.success(f"{prefix}: {message}")


async def main() -> None:
    with TemporaryDirectory(prefix="lclang-cli-tutorial-") as directory:
        path = Path(directory) / "message.lclcfg"
        path.write_text(
            "prefix: 'Hello'\n"
            "target: 'world'\n"
            'message: f"{prefix}, {target}!"\n',
            encoding="utf-8",
        )
        application = CliEntrance(
            CommandGroup("root", "Messaging", [send_command]),
            version="1.0.0",
        )
        output = io.StringIO()
        with redirect_stdout(output):
            status = await application.run(
                [
                    "python",
                    "message.py",
                    "send",
                    "--config",
                    str(path),
                    "--override",
                    "message",
                    "LCL[prefix + ', team!']",
                    "--dryrun",
                ]
            )
        assert status == 0, output.getvalue()
        assert output.getvalue() == "would send: Hello, team!\n", repr(
            output.getvalue()
        )


asyncio.run(main())
```

The config first defines `prefix`, `target`, and a derived `message`. The lazy
CLI override replaces the whole `message` definition and reads `prefix` from
the lower config layer, yielding `Hello, team!`. `--dryrun` makes the handler
choose `would send`, and the successful result produces the asserted output and
zero status.

Precedence rises from preset to command defaults, config definitions, CLI
overrides, and reserved runtime values. Here the whole `message` definition is
replaced by a valid `LCL[...]` override; that lazy override can still read
`prefix` from the config layer. Ordinary override values are literal strings,
and a valueless override is Boolean `True`. Because definitions evaluate in
their owning Frame, overriding only `target` would not rewrite the already
config-owned `message` definition's lexical lookup.

Override keys may be qualified, for example
`--override service.port 9443` or
`--override service.port "LCL[base_port + 1]"`. The complete key participates
in the same Frame precedence and scoped validation as configuration and Python
values. A `ParameterDoc` may use that same qualified name, so generated help
and required-value checks describe the exact scoped leaf. `LCL[FRAME_PROXY]`
remains valid low-level syntax for explicitly declaring a prefix, but ordinary
configuration should omit it because qualified leaves infer their prefixes.

`SUCCESS`, `FAILURE`, and `EXCEPTION` map to exit statuses `0`, `1`, and `2`.
Help, version, invalid arguments, logging, and the built-in `builtins`,
`parse_lcl`, and `eval_lcl` commands use the same deterministic routing model.
Both expression commands document an optional `FORCE` Boolean override. Exact
valueless `-o FORCE` requires an exact `RESULT=LCL[...]` value to contain valid
LCL; syntax failures return status `2` with the structured parse error, complete
RESULT token, and an underline at the failing span. Unwrapped RESULT values,
non-RESULT overrides, and assigned FORCE values retain permissive literal
fallback. A masked `RESULT!` redacts the diagnostic excerpt.

CLI overrides are also available while a configuration loader evaluates a
dynamic `using f"..."` target. The same override is reused in the final Frame,
so it can select a file from the prior source context and remain the runtime
winner.

Logger configuration occupies the `logger` scope. A configuration file can set
`logger.log_dir`, `logger.log_file_name`, `logger.log_level`, and
`logger.log_format`; command parameters remain separate from these framework
settings. Calls to `context.logger.info(...)` print their rendered messages to
stdout. Calls to `context.logger.debug(...)` do the same only when `--verbose`
is present, while `context.logger.error(...)` always prints to stderr. Console
logging remains active when file logging is disabled, and the configured file
level never changes console visibility. File and console application handlers
use the same `logger.log_format`. A custom format must retain the timestamp,
level, filename, line number, function, and message fields used by the default
structured format. `%(args)s` is neither present nor required. When a file is
enabled, its first record reports the bound path immediately after the handler
is installed; the remaining audit preamble then records the centered execution
banner, exact raw command line, and masked winning configuration.
Applications that only need the same file-logging policy can instead import
`LogConfig` and `create_logger` from `lclang.utils`; this standalone utility
does not require CLI routing.

Every invocation injects seven reserved values before logger configuration is
evaluated. `__as_of_date__` is the Python `date`, `__dryrun__` and
`__verbose__` are Booleans, `__ymd__` is the as-of date in `YYYYMMDD` form,
`__execution_timestamp__` is the local execution time in `YYYYMMDDHHmmss`
form, `__command__` is the selected leaf command name, and `__cli_params__` is
the immutable `CliParams`. Their public Python key constants avoid repeating
these strings in integrations. Configuration can use the names directly to
choose behavior and deterministic log filenames:

```python
from lclang.cli import (
    RUNTIME_AS_OF_DATE_KEY,
    RUNTIME_CLI_PARAMS_KEY,
    RUNTIME_COMMAND_KEY,
    RUNTIME_DRYRUN_KEY,
    RUNTIME_EXECUTION_TIMESTAMP_KEY,
    RUNTIME_VERBOSE_KEY,
    RUNTIME_YMD_KEY,
)
```

```lclcfg
logger.log_file_name: f"{__command__}-{__ymd__}-{__execution_timestamp__}.log"
```

## Trace parsing and evaluation

Place `--verbose` after a leaf command to follow top-level parsing, value
lookup provenance, caching, fallbacks, and evaluation without changing normal
stdout:

```console
python -m lclang.cli eval_lcl --verbose -o RESULT "LCL[40 + 2]"
```

Internal trace lines go to stderr. When file logging is enabled, the invocation
log also receives setup records buffered before its effective configuration was
known and all later trace records. Values use bounded one-line `(type) value`
representations. Mark a binding name with one trailing `!`, such as
`api_token!: load_token()` in configuration or `-o api_token! value`, to render
that exact name's expressions, values, results, and failures as `*masked*`.
References use `api_token` without the marker. Derived values require their own
marker, and application-authored log messages remain the handler's
responsibility.

Enabled invocation logs begin with four audit records in order: the absolute
log path; one multi-line 51-character execution banner; the raw argv as JSON;
and one multi-line, sorted, aligned execution configuration. Normal parsing
preserves exact token order and option spellings. Masked override payloads use
`*masked*`; manually created `CliParams` without raw argv fall back to a
reconstructed sequence.

Execution-config rows are the union of declared command parameters and final
configuration-file definitions. Missing optional parameters and unrelated
runtime defaults are omitted, while configured logger variables remain visible.
Each row shows only the winning binding: canonical LCL source for a definition,
or a bounded typed representation for a direct Python or CLI value. Masked
definitions show only `*masked*`; masked direct values retain their type. This
inspection is lazy, so it neither evaluates expressions nor populates Frame
caches. The default file format is a stable pipe-delimited record containing
timestamp, severity, logger, source location, function, and rendered message.

`--verbose` has no short spelling because `-v/--version` remains the root
version operation. Like other common options, verbose belongs after the selected
command. An override still treats its optional next token literally, including
`--verbose`; place the verbose flag before a valueless override.

[Previous: Dependency analysis](08-dependency-analysis.md) | [Next: Workflow status](10-workflow-status.md) | [Return to the series introduction](README.md)
