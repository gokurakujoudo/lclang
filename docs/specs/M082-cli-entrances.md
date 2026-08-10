# M082: commands, decorators, and command groups

## Goal

Turn exactly typed async Python handlers into immutable commands and compose
commands into validated nested groups without executing user code.

## Module and test layout

- Declarations live in `pylcl/cli/commands.py`; signature and docstring handling
  may be split into focused sibling modules.
- Tests live in `tests/cli/test_commands.py`.
- Every production callable/value class, public or private, follows the complete
  English rST docstring contract; modules stay below 200 lines.

## Contract

- Module-level `cli.command(name=None, summary=None, parameter_docs=(),
  preset=None)` returns a decorator whose result is a `Command`; the original
  function remains available as `Command.handler`.
- A handler must be an async function with exactly one parameter named and
  annotated `context: CliContext` and return annotation `CliResult`. Resolve
  postponed annotations and reject all other signatures at decoration time.
- The default command name drops one trailing `_command`; command and group names
  match `[a-z][a-z0-9_]*`. The default one-line summary collapses handler prose
  before the first rST field or directive.
- Commands snapshot ordered unique `ParameterDoc` values and a shallow preset.
  Parameter/log/runtime reserved-name conflicts fail during declaration.
- `CommandGroup(name, description, commands)` snapshots commands/groups, rejects
  invalid child types and sibling-name collisions, and preserves declaration
  order. The entrance root group is a descriptive container, not an argv segment.
- Declaration performs no handler call, import discovery, config load, Frame
  construction, logger setup, event-loop creation, or output.

## TDD matrix

- Sunny: decorate explicit/default-named handlers, extract rST summaries, and
  assemble nested groups with stable ordering.
- Rainy: reject every incompatible signature, invalid/default-empty name,
  duplicate parameter/child, reserved name, and unsupported child type.
- Composite-complex: detach mutable parameter/preset/child inputs and reuse one
  handler in independent nested application graphs without shared state.

## Completion evidence

Record signature RED cases, focused GREEN suite, strict mypy/doc checks, full
quality coverage, and date in `progress.md`.
