# M091: cross-platform CLI integration tests

## Goal

Prove the CLI contract is stable on Windows and POSIX without relying on shell
quoting folklore, terminal capabilities, locale, or repository-relative imports.

## Module and test layout

- No new feature module is planned; fixes remain in their owning CLI/config
  modules.
- In-process cases live in `tests/cli/test_platform.py`; subprocess helpers and
  installed smoke cases live in `tests/cli/platform_support.py` and release tests.
- Any production change keeps modules below 200 lines and documents all private
  and public callables/value classes with complete English rST docstrings.

## Contract

- In-process tests pass argv arrays directly; subprocess tests never build a
  command through `shell=True`. Each token is preserved exactly by the host API.
- The matrix covers Windows and POSIX path separators, drive-letter/absolute and
  relative paths, spaces, quotes as literal token data, leading dashes after `--`,
  Unicode filenames/argv/environment/output, and CRLF/LF input.
- stdout and stderr are captured separately as text and exit codes are asserted.
  Help output remains newline-deterministic and contains no ANSI escape sequences.
- Filesystem tests use temporary roots and explicit resolvers, never change global
  CWD for concurrent tests, and close all files/tasks before cleanup.
- CI must run supported Python 3.14+ on Windows and Linux. Platform skips require
  a named unavailable capability and cannot hide shared contract failures.

## TDD matrix

- Sunny: execute the common argv/output/status corpus in process and subprocess
  on both platform families.
- Rainy: cover missing/unreadable paths, invalid UTF-8 files, broken output
  streams, interrupts, option-looking paths, and cleanup failures.
- Composite-complex: clean-install then load nested config under spaced Unicode
  paths, pass quote/dash/newline-like tokens without a shell, dry-run and execute.

## Completion evidence

`progress.md` records OS/Python matrix jobs, exact commands, case counts, outputs,
coverage/full quality result, and verification date.
