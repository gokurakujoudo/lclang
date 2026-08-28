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

<!-- lclang-tutorial-exec -->
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

<!-- lclang-tutorial-exec -->
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
optionally declares a prefix.

`SUCCESS`, `FAILURE`, and `EXCEPTION` map to exit statuses `0`, `1`, and `2`.
Help, version, invalid arguments, logging, and the built-in `builtins`,
`parse_lcl`, and `eval_lcl` commands use the same deterministic routing model.

## Trace parsing and evaluation

Place `--verbose` after a leaf command to follow top-level parsing, value
lookup provenance, caching, fallbacks, and evaluation without changing normal
stdout:

```console
python -m lclang.cli eval_lcl --verbose -o RESULT "LCL[40 + 2]"
```

Trace lines go to stderr. When file logging is enabled, the invocation log also
receives setup records buffered before its effective configuration was known and
all later trace records. Values use bounded one-line `(type) value`
representations. Mark a binding name with one trailing `!`, such as
`api_token!: load_token()` in configuration or `-o api_token! value`, to render
that exact name's expressions, values, results, and failures as `*masked*`.
References use `api_token` without the marker. Derived values require their own
marker, and application-authored log messages remain the handler's
responsibility.

Enabled invocation logs begin with four audit records: the selected command,
absolute log path, a normalized command line, and the CLI-owned execution
configuration (`as_of_date`, `dryrun`, `verbose`, config path, and overrides).
Override values use `*masked*` whenever their exact binding is masked by the
command, config, or override marker. This preamble is written before buffered
verbose traces and does not evaluate command parameters. The default file
format is a stable pipe-delimited record containing timestamp, severity, logger,
source location, function, rendered message, and original logging arguments.

`--verbose` has no short spelling because `-v/--version` remains the root
version operation. Like other common options, verbose belongs after the selected
command. An override still treats its optional next token literally, including
`--verbose`; place the verbose flag before a valueless override.

[Previous: Dependency analysis](08-dependency-analysis.md) | [Next: Workflow status](10-workflow-status.md)
