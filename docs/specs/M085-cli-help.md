# M085: deterministic structured help

## Goal

Render entrance, group, command, and usage-error help as structured plain text
without terminal probing, ANSI codes, configuration, or execution.

## Module and test layout

- Rendering lives in `pylcl/cli/help.py`; immutable render values may live in a
  focused sibling module.
- Tests live in `tests/cli/test_routing_help.py` and assert complete stable output.
- Every private/public production callable and value class has a full English
  rST docstring; each source module remains below 200 lines.

## Contract

- Renderers return Unicode text ending in one newline at fixed width 100. They
  use standard-library wrapping and aligned sections, with no Rich dependency.
- Root/group help shows usage, normalized description, ordered commands/groups,
  and applicable help/version options. Root usage omits the root-group name.
- Command help shows usage, one-line summary, common options, and a configuration
  parameter table: name, stable displayed type, required state, default, and
  normalized description. `None` defaults display as absent.
- Canonical options are `-c, --config <file>`,
  `-o, --override <key> [<value>]`, `-a, --as-of <YYYYMMDD>`,
  `-wif, --dryrun`, and `-h, --help`; root adds `-v, --version`.
- Explicit help writes stdout and returns 0 without config, Frames, logging, or a
  handler. Usage errors write a concise `error:` plus nearest help to stderr and
  return 2.
- Rendering never consults terminal width, color capability, locale, environment,
  CWD, configuration, or logging state and emits no ANSI/control sequences.

## TDD matrix

- Sunny: snapshot root, nested-group, and command help with aliases, types,
  required markers, defaults, and version.
- Rainy: prove control characters, terminal state, locale, config/log paths, and
  handler side effects cannot leak into help; verify exact error-stream behavior.
- Composite-complex: render a nested Unicode application with long wrapped prose,
  mixed parameter metadata, repeated overrides, and nearest-scope usage errors.

## Completion evidence

Record RED snapshots/structural checks, focused GREEN results, full quality
coverage, and date in `progress.md`.
