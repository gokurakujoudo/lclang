# M089: help and version built-ins

## Goal

Provide collision-safe help and version operations at their documented routing
scopes without introducing commands or application discovery.

## Module and test layout

- Built-in recognition and dispatch live in `pylcl/cli/routing.py` and
  `pylcl/cli/run.py`.
- Tests live in `tests/cli/test_routing_help.py` and `tests/cli/test_run.py`.
- All production callables/value classes, private or public, use complete English
  rST docstrings and each source module remains under 200 lines.

## Contract

- `-h/--help` is recognized at root, every group, and a selected command.
  `-v/--version` is recognized only as the sole root operation.
- Version output is `<script basename> <CliEntrance.version>\n`; the version
  defaults to `0.0.0` and must be non-empty text.
- Built-in spellings are reserved from command/group names and parameter parsing.
  Arguments after a version request are usage errors rather than ignored.
- Help/version construct no `CliParams`, load no config, create no Frames/log
  paths, invoke no handler, mutate no environment, and perform no discovery.
- There is no `config-check`, dryrun planner, automatic language/config command,
  or policy for disabling/replacing built-ins.

## TDD matrix

- Sunny: invoke root/group/command help and both version aliases with exact output
  and zero status.
- Rainy: reject collisions, misplaced/extra version tokens, and demonstrate every
  config/Frame/logger/handler short-circuit sentinel remains untouched.
- Composite-complex: exercise nested Unicode groups, static missing config text,
  enabled temporary logging settings, and all built-in scopes in one entrance.

## Completion evidence

Ledger RED/GREEN commands, short-circuit assertions, full quality coverage, and
verification date.
