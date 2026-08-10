# M084: nested command-group routing

## Goal

Traverse one immutable root group, select exactly one leaf command, and pass its
remaining tokens to the common-option parser.

## Module and test layout

- Routing and route-result models live in `pylcl/cli/routing.py`.
- Tests live in `tests/cli/test_routing_help.py` and `tests/cli/test_run.py`.
- All production callables and value classes use complete English rST docstrings,
  including private ones; source files stay below 200 lines.

## Contract

- Routing begins after executable and script tokens. The root group's own name is
  never consumed; every nested group and the leaf command contributes one path
  segment to `CliParams.command`.
- Match child names exactly and case-sensitively in declaration order. A group is
  never executable and a command is always a leaf.
- `-h/--help` at root, group, or command selects help for that exact scope.
  `-v/--version` is recognized only at the root. Version with extra tokens is a
  usage error.
- Missing or unknown child names report the nearest group and deterministic
  available names. Bare tokens after a selected command are parser errors.
- Routing returns the selected command, consumed tuple, remaining tokens, script
  display label, and token offset. It performs no option conversion, config load,
  Frame/logger creation, handler call, or output.

## TDD matrix

- Sunny: route root commands, siblings, and three-level nested commands with exact
  paths, remainders, and offsets; select help/version scopes.
- Rainy: report missing commands, unknown names, case mismatch, group-only paths,
  misplaced version, and extra version tokens.
- Composite-complex: route overlapping snake_case paths followed by mixed common
  options whose values resemble group/command names.

## Completion evidence

Ledger route RED/GREEN commands, exact paths/scopes, full quality coverage, and
completion date.
