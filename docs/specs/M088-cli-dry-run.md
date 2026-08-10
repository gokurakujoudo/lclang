# M088: dryrun pass-through semantics

## Goal

Expose an invocation dryrun signal to the command without changing framework
setup, execution, output, or side-effect policy.

## Module and test layout

- Dryrun parsing remains in the common parser and runtime exposure remains in
  binding/context modules; no standalone plan or serializer module is added.
- Tests live in `tests/cli/test_parser.py`, `tests/cli/test_binding.py`, and
  `tests/cli/test_run.py`, with side-effect sentinels local to their cases.
- Production modules stay below 200 lines and every callable/value class,
  including private ones, has a full English rST docstring.

## Contract

- `-wif/--dryrun` sets `CliParams.dryrun`, `CliContext.dryrun`, and the Frame host
  value `dryrun` to `True`; omission sets all three to `False`.
- Dryrun performs the same config loading, Frame construction, required checks,
  logging setup, handler invocation, result mapping, and cleanup as a normal run.
- The framework neither suppresses side effects nor renders a plan. The handler
  is solely responsible for consulting the flag before an external side effect.
- Help/version remain their normal short circuits even when dryrun text appears
  in help; no config or logger is initialized for those operations.

## TDD matrix

- Sunny: prove one handler observes matching false/true values in params, context,
  and Frame and can deliberately skip a call when true.
- Rainy: prove a handler that ignores dryrun still executes its side effect, and
  normal parsing/config/handler failures keep their standard statuses.
- Composite-complex: run normal and dryrun variants over the same static config,
  temporary log root, lazy override, and mocked connectivity; compare setup,
  records, output, cleanup, and only the handler-controlled external call.

## Completion evidence

Record RED side-effect sentinels, GREEN pass-through assertions, full quality
coverage, and date in `progress.md`.
