# M093: CLI result shortcuts and module commands

## Goal

Add concise success/failure result constructors and make `python -m pylcl.cli`
a useful zero-dependency entrance for inspecting and evaluating one `RESULT`
binding through the same CLI Frame pipeline available to user scripts.

## Module and test layout

- `CliResult` shortcuts remain in `pylcl/cli/models.py`.
- Built-in handlers and their entrance live in `pylcl/cli/application.py`; the
  minimal process adapter lives in `pylcl/cli/__main__.py`.
- Behavioural tests live in `tests/cli/test_models.py` and
  `tests/cli/test_module_entrance.py`; subprocess calls pass token arrays without
  `shell=True`.
- Production modules stay below 200 lines and every callable/value class has a
  complete English rST docstring.

## Contract

- `CliResult.success(msg)` returns `CliResult(SUCCESS, msg)` and
  `CliResult.fail(msg)` returns `CliResult(FAILURE, msg)`. Both retain constructor
  validation, accept Unicode strings including empty text, and return the actual
  class selected by the class method.
- `python -m pylcl.cli` runs a root `CliEntrance` using the installed package
  version. It offers exactly `parse_lcl` and `eval_lcl` as leaf commands; normal
  root/command help, version, config, override, as-of, dryrun, logging, streams,
  cleanup, and statuses remain framework-owned.
- Both commands declare required parameter `RESULT`. Its effective definition may
  come from a parameter default, config file, or command-line override using the
  existing precedence rules. Other bindings such as `a` and `b` need no command
  declaration and may come from config or repeated `-o` options.
- `parse_lcl` calls `context.frame.inspect_variable("RESULT")` and returns the
  newline-joined `VariableInspectionTree.to_lines()` representation. It performs
  no evaluation, so `LCL[1 / 0]` and missing dependency leaves are rendered rather
  than executed; a missing `RESULT` remains a usage failure before the handler.
- `eval_lcl` awaits `context.frame.get("RESULT")` exactly once and returns
  `str(value)` as a successful description. Ordinary literal override values stay
  strings, so `-o a 100 -o b 200 -o RESULT LCL[a+b]` prints `100200`. Evaluation
  failures use the existing exception status `2` and stderr/log traceback policy.
- Importing `pylcl.cli` remains inert. Only executing `pylcl.cli.__main__` adapts
  ambient argv, creates an event loop, runs the entrance, and raises `SystemExit`
  with its returned integer status. No console-script metadata is added.

M099 extends this historical two-command entrance with the non-evaluating
`builtins` inventory command; `parse_lcl` and `eval_lcl` retain this contract.

## TDD matrix

- Sunny: validate both result shortcuts; inspect a two-leaf expression without
  caching it; evaluate two literal string overrides to `100200`; render module
  root/command help and version.
- Rainy: reject non-string shortcut messages, report missing `RESULT`, render a
  missing static dependency without evaluation, and map an evaluation error to
  status `2` and stderr.
- Composite-complex: execute `python -m pylcl.cli` in a subprocess with Unicode
  and option-looking literal values, a lazy `RESULT`, exact stdout/stderr, and no
  shell parsing or default log artifacts.

## Completion evidence

Record the focused RED/GREEN commands, shortcut and subprocess case counts,
non-evaluation assertion, full quality result, and verification date in
`progress.md` before marking this milestone DONE.
