# M092: CLI tutorial, documentation, and 0.3 release gate

## Goal

Teach users to build configuration-driven Python-script CLIs, synchronize the
verified API in both languages, and validate the 0.3 artifacts.

## Module and test layout

- The English CLI tutorial lives under `docs/tutorials/` and an equivalent
  Chinese tutorial under `doc_cn/`; indexes and both root READMEs link them.
- Executable documentation checks live in `tests/cli/test_tutorial.py`; build/install
  checks reuse established release scripts and static sample/config fixtures.
- Any production edits preserve sub-200-line modules and complete English rST
  docstrings for every public/private callable and value class.

## Contract

- The tutorial begins with a complete independently executable user `.py` script
  using `@cli.command`, `ParameterDoc`, `CommandGroup`, `CliEntrance`, and
  `asyncio.run`. It explains the executable/script/route/argument token model.
- Key concepts cover immutable params/context/results, exact async handler
  signature, snake_case routing, root-group containment, common options, strict
  as-of dates, dryrun responsibility, result/output/status mapping, and help/version.
- The methodology section teaches preset -> defaults -> config -> overrides ->
  runtime precedence, required non-evaluating checks, literal versus successfully
  parsed `LCL[...]` overrides, lazy `frame.get`, resource ownership, logging
  defaults/overrides, and trusted-configuration scope.
- Examples include root and nested commands, static `.lclcfg` with `using`,
  literal and deferred overrides, as-of use, a side-effect-safe dryrun handler,
  enabled temporary/file logging, success/failure/exception results, direct
  full-argv testing, and exact help/version invocations. Each includes description,
  expected stdout/stderr/status, and relevant log behavior.
- Tutorial tests extract/execute every marked Python example. Runtime config text
  is static with each case, and enabled logs are written only beneath automatically
  cleaned temporary directories.
- `pyproject.toml`, `pylcl.__version__`, changelog, `pylcl.cli` API inventory, and
  documentation become exactly 0.3.0. No root-package CLI re-exports or console
  entry point are added.
- Build/inspect wheel and sdist, install each without dependencies in separate
  clean Python 3.14+ environments, and run import, help, version, nested success,
  usage failure, dryrun, logging, and handler-exception sample-script smokes.
- The release gate includes strict mypy, Ruff, source/docstring checks, all tests
  with branch threshold, bilingual link/example parity, artifact-content audit,
  and Windows/Linux CI evidence.

## TDD matrix

- Sunny: execute all bilingual examples and clean-install success/logging matrices
  from both artifacts.
- Rainy: fail on stale versions, broken links, translation/API drift, dynamic
  config generation, logs outside temporary roots, wrong streams/statuses,
  undeclared exports, console metadata, or repository leakage.
- Composite-complex: clean-install, run the tutorial's Unicode nested command with
  static includes, layered values, lazy override, as-of/dryrun and temporary log,
  then verify output, dependencies, status, traceback behavior, and cleanup.

## Completion evidence

Record exact tutorial/build/inspect/install/smoke/full-quality commands, OS
results, coverage/counts, artifact names/hashes, and completion date in
`progress.md`.
