# M084: command routing

## Goal

Select exactly one entrance from an application and pass only its remaining
tokens to the fixed-arity parser.

## Module and test layout

- Routing and route-result models live in `pylcl/cli/routing.py`.
- Tests live in `tests/cli/test_routing.py` with application fixtures in the
  shared CLI support module.
- All production callables and value classes use complete English rST docstrings,
  including private ones; source files stay under 200 lines.

## Contract

- Command paths are matched from the beginning of argv by exact case-sensitive
  segment. The longest declared path wins.
- An application may declare one explicit default entrance at the empty path.
  It receives argv when no command segment matches; otherwise unknown first
  segments raise `CliRouteError` with deterministic suggestions.
- A parent entrance may coexist with child paths. It wins only when argv ends at
  the parent or the next token begins its parameter grammar; an exact child
  segment always routes to the child.
- `--` stops command matching as well as option matching and belongs to the
  selected entrance's remaining argv.
- Routing returns immutable selected entrance, consumed path, remaining tokens,
  and token offset. It performs no conversion, I/O, config load, or execution.

## TDD matrix

- Sunny: route root, parent, deepest child, sibling, and default entrances with
  exact remaining argv/offset.
- Rainy: report unknown commands, no applicable default, case mismatch, and
  construction-time ambiguity with ordered suggestions.
- Composite-complex: route overlapping three-level paths mixed with parent
  positionals, option-looking tokens, Unicode arguments, and `--`.

## Completion evidence

Ledger route RED/GREEN commands, ambiguity/suggestion checks, full quality
coverage, and completion date.
