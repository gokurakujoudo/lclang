# M091: cross-platform CLI integration tests

## Goal

Prove Python-script CLI behavior is stable on Windows and POSIX without shell
parsing, terminal assumptions, mutable runtime config generation, or leaked logs.

## Module and test layout

- No new feature module is planned; fixes remain in their owning CLI/config
  modules.
- In-process cases live in `tests/cli/test_platform.py`; subprocess support lives
  in `tests/cli/platform_support.py` and release tests.
- All runtime `.lclcfg` contents are static fixtures declared beside their cases.
  Each filesystem case materializes those fixtures under a separate temporary
  root; every enabled log directory is a child of an automatically cleaned
  temporary directory.

## Contract

- In-process tests pass full argv arrays directly; subprocess tests never use
  `shell=True`. Each token is preserved exactly by the host API.
- Cover Windows/POSIX separators, drive/absolute/relative paths, spaces, literal
  quote characters, Unicode filenames/argv/output, and option-looking values.
- stdout/stderr remain separate text streams; statuses and ANSI-free fixed-width
  help are exact and newline deterministic.
- Static config fixtures cover valid roots/includes and fixed invalid inputs;
  tests do not generate configuration semantics dynamically from execution state.
- Log assertions use only per-test temporary roots, close handlers before cleanup,
  and verify disabled logging creates nothing.
- CI runs supported Python 3.14+ on Windows and Linux. Skips name an unavailable
  platform capability and cannot hide shared behavior failures.

## TDD matrix

- Sunny: execute the common argv/output/status/log corpus in process and
  subprocess on both platform families.
- Rainy: cover missing/unreadable/static-invalid configs, broken output/log paths,
  interrupts, option-looking values, and cleanup failures.
- Composite-complex: clean-install, run a nested command from a spaced Unicode
  script, load a static include graph, apply literal/LCL overrides, dryrun and
  execute, then prove temporary logs and config materialization clean up.

## Completion evidence

`progress.md` records OS/Python matrix jobs, exact commands, case counts, outputs,
coverage/full quality result, and verification date.
