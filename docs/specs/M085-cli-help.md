# M085: deterministic help and usage rendering

## Goal

Render application, command, and usage-error help without terminal probing or
execution side effects.

## Module and test layout

- Rendering lives in `pylcl/cli/help.py`; immutable render options may live in
  `pylcl/cli/help_model.py`.
- Tests live in `tests/cli/test_help.py` and assert complete stable output.
- Every private/public production callable and value class has a full English
  rST docstring; each source module remains below 200 lines.

## Contract

- `render_help(application, entrance=None, *, width=80)` returns Unicode text
  ending in one newline. Width is explicit and must be at least 40.
- Application help lists usage, summary, commands, and built-ins in declaration
  order. Entrance help lists command usage, positionals, options/aliases,
  required markers, defaults safe for display, and wrapped descriptions.
- Usage syntax is canonical: required values use angle brackets, optional values
  brackets, options their declared metavar, and literal `--` only when useful.
- Rendering never consults terminal width, color capability, locale, environment,
  or current directory. It emits no ANSI codes and normalizes embedded whitespace.
- Usage errors render a concise `error:` line, relevant usage, and `Try ... --help`;
  sensitive default values may be marked hidden and never rendered.

## TDD matrix

- Sunny: snapshot root/command help at narrow and wide widths with aliases and
  visible defaults.
- Rainy: reject invalid widths and prove hidden defaults, control characters,
  terminal state, and locale cannot leak into output.
- Composite-complex: render a nested Unicode application with long wrapped help,
  required/optional arguments, negative flags, built-ins, and a usage error.

## Completion evidence

Record RED snapshots/structural checks, focused GREEN results, full quality
coverage, and date in `progress.md`.
